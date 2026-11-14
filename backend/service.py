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
from pathlib import Path
from fastapi import FastAPI, Query, Request, Response
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.store import GameStore, GameError

CLASSES=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck']

def _read_json(path:Path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return None


class NoteInput(BaseModel):
    text: str = Field(max_length=400)

def make_app(store:GameStore,state_root:Path):
    state_root=Path(state_root)
    secret=os.getenv('TDM_COOKIE_SECRET','').encode()
    if len(secret)<32:
        raise RuntimeError('Set TDM_COOKIE_SECRET to at least 32 random characters')
    publish_images=os.getenv('TDM_PUBLISH_IMAGES')=='true'
    app=FastAPI(title='Training Data Market API',version='0.4.1',docs_url=None,redoc_url=None)

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
        if not round_data:return {'mode':'UNINITIALIZED','metrics':None,'round':None}
        stats=_read_json(state_root/'metrics'/(round_data['checkpoint']+'.json'))
        public={'id':round_data['id'],'status':round_data['status'],
                'targets':[round_data['target_a'],round_data['target_b']],
                'checkpoint':round_data['checkpoint'],'opened_at':round_data['opened_at'],
                'locked_at':round_data['locked_at']}
        return {'mode':'LIVE' if stats else 'UNINITIALIZED','metrics':stats,'round':public}

    @app.get('/v1/samples')
    def samples(page:int=Query(1,ge=1),limit:int=Query(48,ge=1,le=48),
                label:int|None=Query(None,ge=0,le=9),wrong_only:bool=False,
                query:str=Query('',max_length=100)):
        current=store.current_round()
        if current is None:raise GameError('training dataset not initialized',503)
        prediction_data=_read_json(state_root/'predictions'/(current['checkpoint']+'.json'))
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
                'image_rights_approved':publish_images}

    @app.get('/v1/samples/{sample_id}')
    def sample_detail(sample_id:int):
        info=store.get_sample(sample_id)
        current=store.current_round()
        prediction_data=_read_json(state_root/'predictions'/(current['checkpoint']+'.json')) if current else None
        pred=(prediction_data or {}).get('samples',{}).get(str(sample_id))
        return {**info,'prediction':pred,'class_name':CLASSES[info['label']],
                'image_url':f'/v1/samples/{sample_id}/image' if publish_images else None}

    @app.get('/v1/samples/{sample_id}/image')
    def image(sample_id:int):
        if not publish_images:raise GameError('image publication not approved',403)
        classes=store.get_classes()
        if sample_id not in classes:raise GameError('image is not eligible',404)
        from backend.ml import CombinedCIFAR
        from PIL import Image
        root=Path(os.getenv('TDM_DATA_ROOT','data'))
        ds=CombinedCIFAR(root)
        x,y=ds[sample_id]
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

    @app.get('/v1/rounds/history')
    def history():
        return {'items':[{'id':r['id'],'status':r['status'],
                          'targets':[r['target_a'],r['target_b']],
                          'checkpoint':r['checkpoint'],'opened_at':r['opened_at']}
                         for r in store.list_rounds(20)]}

    @app.put('/v1/rounds/{round_id}/note')
    def save_note(round_id:str,payload:NoteInput,response:Response,request:Request):
        user=issue_session(request,response)
        return {'status':store.set_note(round_id,user,payload.text)}

    @app.get('/v1/rounds/{round_id}/results')
    def results(round_id:str):
        obj=store.get_round(round_id)
        if obj['status']!='PUBLISHED':return {'status':obj['status'],'results':None}
        return {'status':'PUBLISHED','results':json.loads(obj['result_json'])}

    @app.post('/v1/admin/rounds/{round_id}/lock')
    def lock_round(round_id:str,request:Request):
        require_admin(request)
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
    @app.get('/demo.html')
    def demo_html():return FileResponse(Path(__file__).resolve().parent.parent/'index.html',media_type='text/html')
    return app


def get_app():
    root=Path(os.getenv('TDM_STATE_ROOT','state'))
    store=GameStore(root/'votes.sqlite3')
    store.initialize()
    return make_app(store,root)

app=get_app() if os.getenv('TDM_COOKIE_SECRET') else None
