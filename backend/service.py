"""Same-origin voting API for the local training worker.

Local pilot uses signed pseudonymous browser sessions, NOT verified accounts.
For a public site, replace issue_session with Sites' actual authenticated identity.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
import time
from threading import Lock
from pathlib import Path
from fastapi import FastAPI, Query, Request, Response
from pydantic import BaseModel, Field, StrictInt
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.store import GameStore, GameError

CLASSES=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck']

def _read_json(path:Path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return None


def _round_artifact(root:Path,folder:str,round_data:dict):
    # v0.9 snapshots are keyed by round; v0.8 checkpoints are a read-only fallback.
    return (_read_json(root/folder/(round_data['id']+'.json')) or
            _read_json(root/folder/(round_data['checkpoint']+'.json')))


class NoteInput(BaseModel):
    text: str = Field(max_length=400)

class ForecastInput(BaseModel):
    probability_pct: StrictInt = Field(ge=5, le=95)

def make_app(store:GameStore,state_root:Path):
    state_root=Path(state_root)
    secret=os.getenv('TDM_COOKIE_SECRET','').encode()
    if len(secret)<32:
        raise RuntimeError('Set TDM_COOKIE_SECRET to at least 32 random characters')
    manifest=_read_json(state_root/'manifest.json') or {}
    demo=manifest.get('dataset')=='SYNTHETIC_PIXEL_ART'
    # Never serve natural-image datasets on the strength of a demo switch.
    demo_enabled=demo and os.getenv('TDM_DEMO_MODE')=='true'
    # An environment switch alone is not a legal/publication approval.
    natural_rights_ok=(manifest.get('dataset')=='CIFAR-10' and
                       manifest.get('image_rights_status')=='APPROVED')
    publish_images=demo_enabled or (natural_rights_ok and os.getenv('TDM_PUBLISH_IMAGES')=='true')
    app=FastAPI(title='Training Data Market API',version='0.4.1',docs_url=None,redoc_url=None)
    # CIFAR-10 loads all training images into memory at construction time.
    # Reusing one immutable dataset per API process avoids a full reload for
    # every 32x32 image card. Guard cold startup against parallel requests.
    image_dataset = None
    image_dataset_lock = Lock()

    def get_image_dataset():
        nonlocal image_dataset
        if image_dataset is None:
            with image_dataset_lock:
                if image_dataset is None:
                    from backend.ml import CombinedCIFAR
                    from backend.demo_data import SyntheticPixelArt
                    root = Path(os.getenv('TDM_DATA_ROOT', 'data'))
                    image_dataset = (SyntheticPixelArt(manifest.get('seed', 20261115))
                                     if demo_enabled else CombinedCIFAR(root))
        return image_dataset


    @app.exception_handler(GameError)
    async def game_error_handler(request:Request,exc:GameError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code,content={'error':str(exc),'request_id':secrets.token_hex(8)})

    @app.middleware('http')
    async def enforce_same_origin(request:Request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin=request.headers.get('origin')
            if origin is not None:
                from urllib.parse import urlsplit
                parsed=urlsplit(origin)
                if parsed.netloc.lower()!=request.url.netloc.lower() or parsed.scheme not in ('http','https'):
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=403,content={'error':'origin not allowed'})
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        return response

    def _signed(session_id:str)->str:
        mac=hmac.new(secret,session_id.encode(),hashlib.sha256).hexdigest()
        return f'{session_id}.{mac}'

    def issue_session(request:Request,response:Response)->str:
        raw=request.cookies.get('tdm_session','')
        if raw.count('.')==1:
            identity,provided=raw.split('.',1)
            if len(identity)==32 and all(c in '0123456789abcdef' for c in identity):
                expected=_signed(identity).split('.',1)[1]
                if hmac.compare_digest(provided,expected):return identity
        identity=secrets.token_hex(16)
        response.set_cookie('tdm_session',_signed(identity),max_age=60*60*24*30,
                            secure=os.getenv('TDM_COOKIE_SECURE','false')=='true',
                            httponly=True,samesite='lax',path='/')
        return identity

    def require_admin(request:Request):
        expected=os.getenv('TDM_ADMIN_KEY','')
        if len(expected)<20 or not hmac.compare_digest(request.headers.get('X-Admin-Key',''),expected):
            # refuse even weak admin keys to prevent accidental public exposure
            raise GameError('admin authorization failed',403)

    @app.get('/health')
    def health():return {'ok':True,'initialized':store.current_round() is not None}

    @app.get('/v1/rounds/current')
    def current_round(response:Response,request:Request):
        issue_session(request,response)
        round_data=store.current_round()
        if not round_data:return {'mode':'UNINITIALIZED','metrics':None,'round':None,'vote_summary':None,
                                  'server_time':time.time()}
        stats=_round_artifact(state_root,'metrics',round_data)
        public={'id':round_data['id'],'status':round_data['status'],
                'targets':[round_data['target_a'],round_data['target_b']],
                'checkpoint':round_data['checkpoint'],'opened_at':round_data['opened_at'],
                'closes_at':round_data['closes_at'],'locked_at':round_data['locked_at']}
        return {'mode':('DEMO' if demo else 'LIVE') if stats else 'UNINITIALIZED',
                'dataset_name':manifest.get('dataset'),'metrics':stats,'round':public,
                'vote_summary':store.vote_summary(round_data['id']),
                'server_time':time.time()}

    @app.get('/v1/samples')
    def samples(page:int=Query(1,ge=1),limit:int=Query(48,ge=1,le=48),
                label:int|None=Query(None,ge=0,le=9),wrong_only:bool=False,
                query:str=Query('',max_length=100)):
        current=store.current_round()
        if current is None:raise GameError('training dataset not initialized',503)
        prediction_data=_round_artifact(state_root,'predictions',current)
        preds=(prediction_data or {}).get('samples')
        # Predictions are checkpoint-specific. Avoid attributing obsolete losses to the current model.
        checkpoint=prediction_data.get('checkpoint') if prediction_data else None
        stale=checkpoint!=current['checkpoint']
        if wrong_only and (preds is None or stale):
            raise GameError('predictions are unavailable for the current checkpoint',503)
        phrase=query.strip().lower()
        if phrase and not phrase.isdigit():
            if phrase in CLASSES: label=CLASSES.index(phrase);phrase=''
            else:raise GameError('search must be an image ID or class name',422)
        rows,total=store.samples_page(page,limit,label,wrong_only,preds,search=phrase)
        enriched=[]
        counts=store.get_counts(current['id'])
        for x in rows:
            pred=preds.get(str(x['id'])) if preds and not stale else None
            enriched.append({**x,'class_name':CLASSES[x['label']],
                             'prediction':pred, 'votes':counts.get(x['id'],0),
                             'image_url':f"/v1/samples/{x['id']}/image" if publish_images else None})
        return {'items':enriched,'total':total,'page':page,'limit':limit,
                'checkpoint':checkpoint if not stale else None,
                'predictions_stale':stale or preds is None,
                'image_rights_approved':publish_images,'image_kind':('SYNTHETIC_PIXEL_ART' if demo else 'CIFAR-10')}

    @app.get('/v1/samples/{sample_id}')
    def sample_detail(sample_id:int):
        info=store.get_sample(sample_id)
        current=store.current_round()
        prediction_data=_round_artifact(state_root,'predictions',current) if current else None
        pred=((prediction_data or {}).get('samples',{}).get(str(sample_id))
              if current and prediction_data and prediction_data.get('checkpoint')==current['checkpoint']
              else None)
        return {**info,'prediction':pred,'class_name':CLASSES[info['label']],
                'image_url':f'/v1/samples/{sample_id}/image' if publish_images else None}

    @app.get('/v1/samples/{sample_id}/image')
    def image(sample_id:int):
        if not publish_images:raise GameError('image publication not approved',403)
        classes=store.get_classes()
        if sample_id not in classes:raise GameError('image is not eligible',404)
        from PIL import Image
        x,y=get_image_dataset()[sample_id]
        np_img=(x.permute(1,2,0).mul(255).byte().numpy())
        blob=io.BytesIO();Image.fromarray(np_img).save(blob,'PNG');blob.seek(0)
        return StreamingResponse(blob,media_type='image/png',headers={'Cache-Control':'private, max-age=300'})

    @app.get('/v1/rounds/{round_id}/picks/me')
    def my_picks(round_id:str,response:Response,request:Request):
        user=issue_session(request,response)
        store.get_round(round_id)
        return {'ids':store.get_picks(round_id,user),
                'note':store.get_note(round_id,user),
                'identity_type':'pseudonymous_browser'}

    @app.put('/v1/rounds/{round_id}/picks/{sample_id}')
    def add_pick(round_id:str,sample_id:int,response:Response,request:Request):
        user=issue_session(request,response)
        return {'status':store.set_pick(round_id,user,sample_id)}

    @app.delete('/v1/rounds/{round_id}/picks/{sample_id}')
    def remove_pick(round_id:str,sample_id:int,response:Response,request:Request):
        user=issue_session(request,response)
        return {'deleted':store.delete_pick(round_id,user,sample_id)}

    @app.get('/v1/rounds/{round_id}/forecast/me')
    def my_forecast(round_id:str,response:Response,request:Request):
        user=issue_session(request,response)
        forecast=store.get_forecast(round_id,user)
        row=store.get_round(round_id)
        return {'probability_pct':forecast,
                'editable':row['status']=='OPEN' and row['closes_at'] is not None and time.time()<row['closes_at']}

    @app.put('/v1/rounds/{round_id}/forecast/me')
    def save_forecast(round_id:str,payload:ForecastInput,response:Response,request:Request):
        user=issue_session(request,response)
        return {'status':store.set_forecast(round_id,user,payload.probability_pct),
                'probability_pct':payload.probability_pct}

    @app.get('/v1/game/me')
    def my_game_record(response:Response,request:Request):
        user=issue_session(request,response)
        return store.player_history(user)

    @app.get('/v1/rounds/history')
    def history():
        return {'items':[{'id':r['id'],'status':r['status'],
                          'targets':[r['target_a'],r['target_b']],
                          'checkpoint':r['checkpoint'],'opened_at':r['opened_at'],
                          'closes_at':r['closes_at']}
                         for r in store.list_rounds(20)]}

    @app.put('/v1/rounds/{round_id}/note')
    def save_note(round_id:str,payload:NoteInput,response:Response,request:Request):
        user=issue_session(request,response)
        return {'status':store.set_note(round_id,user,payload.text)}

    @app.get('/v1/rounds/{round_id}/results')
    def results(round_id:str):
        obj=store.get_round(round_id)
        if obj['status']!='PUBLISHED':return {'status':obj['status'],'results':None}
        from backend.forecast import judge_round
        published=json.loads(obj['result_json'])
        return {'status':'PUBLISHED','results':{**published,'forecast_verdict':judge_round(published)}}

    @app.get('/v1/rounds/{round_id}/participation/me')
    def my_participation(round_id:str,response:Response,request:Request):
        """Personal feedback: voted-slot adoption, not causal training contribution."""
        user=issue_session(request,response)
        round_data=store.get_round(round_id)
        recommended=store.get_picks(round_id,user)
        adopted_ids=None
        if round_data['status']=='PUBLISHED' and round_data['result_json']:
            result=json.loads(round_data['result_json'])
            # Old experiments lack vote provenance. Never infer it from the
            # full Community batch: its random-fill portion is not vote-selected.
            if isinstance(result.get('voted_ids'),list):
                voted={int(i) for i in result['voted_ids']}
                adopted_ids=sorted(set(recommended).intersection(voted))
        return {'round_id':round_id,'status':round_data['status'],
                'recommended_ids':recommended,'recommended_count':len(recommended),
                'adopted_ids':adopted_ids,
                'adopted_count':len(adopted_ids) if adopted_ids is not None else None}

    @app.post('/v1/admin/rounds/{round_id}/lock')
    def lock_round(round_id:str,request:Request):
        require_admin(request)
        round_data=store.get_round(round_id)
        # The web API must never shorten a timed community ballot, even for admin.
        # The worker performs the closure after the persisted deadline.
        if round_data['closes_at'] is None or time.time()<round_data['closes_at']:
            raise GameError('voting deadline has not passed',409)
        store.lock_round(round_id)
        return {'status':'LOCKED','round_id':round_id,
                'next_action':'run ML worker: python -m backend.ml train-round --round-id '+round_id}

    @app.get('/')
    def index():
        main=Path(__file__).resolve().parent.parent/'live.html'
        return FileResponse(main,media_type='text/html')
    @app.get('/live.js')
    def live_js():return FileResponse(Path(__file__).resolve().parent.parent/'live.js',media_type='text/javascript')
    @app.get('/styles.css')
    def styles():return FileResponse(Path(__file__).resolve().parent.parent/'styles.css',media_type='text/css')
    @app.get('/live.css')
    def live_css():return FileResponse(Path(__file__).resolve().parent.parent/'live.css',media_type='text/css')
    @app.get('/game.css')
    def game_css():return FileResponse(Path(__file__).resolve().parent.parent/'game.css',media_type='text/css')
    @app.get('/experience.css')
    def experience_css():return FileResponse(Path(__file__).resolve().parent.parent/'experience.css',media_type='text/css')
    @app.get('/app.js')
    def demo_js():return FileResponse(Path(__file__).resolve().parent.parent/'app.js',media_type='text/javascript')
    @app.get('/src/{script}')
    def browser_src(script:str):
        permitted={'arena-view.js','deadline.js','round-flow.js','game-view.js','demo-data.js','selection.js','draft.js'}
        if script not in permitted:raise GameError('script not found',404)
        return FileResponse(Path(__file__).resolve().parent.parent/'src'/script,media_type='text/javascript')
    @app.get('/demo.html')
    def demo_html():return FileResponse(Path(__file__).resolve().parent.parent/'index.html',media_type='text/html')
    return app


def get_app():
    root=Path(os.getenv('TDM_STATE_ROOT','state'))
    store=GameStore(root/'votes.sqlite3')
    store.initialize()
    return make_app(store,root)

app=get_app() if os.getenv('TDM_COOKIE_SECRET') else None
