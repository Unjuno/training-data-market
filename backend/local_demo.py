"""One-command, localhost-only procedural live-learning playground.

This is an actual PyTorch training loop on ORIGINAL SYNTHETIC pixel art.
It is not a CIFAR-10 benchmark and must never be exposed as a public service.
"""
from __future__ import annotations
import argparse, json, logging, os, secrets, threading, time
from pathlib import Path
import uvicorn
from backend.ml import prepare_demo
from backend.service import make_app
from backend.store import GameStore
from backend.worker import poll_once

LOG=logging.getLogger('tdm.local_demo')


def require_loopback(host:str)->str:
    if host not in ('127.0.0.1','localhost','::1'):
        raise ValueError('local demo only supports loopback; deploy authenticated Sites + isolated worker for public use')
    return host


def make_demo_env():
    os.environ['TDM_COOKIE_SECRET']=secrets.token_hex(32)
    os.environ['TDM_ADMIN_KEY']=secrets.token_hex(32)
    os.environ['TDM_DEMO_MODE']='true'
    os.environ['TDM_PUBLISH_IMAGES']='false'
    os.environ['TDM_COOKIE_SECURE']='false'


def main():
    parser=argparse.ArgumentParser(description='Local-only live demo using generated pixel art, NOT CIFAR-10.')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--round-seconds',type=int,default=90)
    parser.add_argument('--state-root',type=Path,default=Path('demo-state'))
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be 1..65535')
    if not 10<=args.round_seconds<=86400:parser.error('round-seconds must be 10..86400')
    make_demo_env()
    os.environ['TDM_ROUND_SECONDS']=str(args.round_seconds)
    state=args.state_root
    if not (state/'manifest.json').exists():
        LOG.warning('Preparing synthetic pixel-art demo dataset (NOT CIFAR-10)')
        print(json.dumps(prepare_demo(state),ensure_ascii=False))
    else:
        data=json.loads((state/'manifest.json').read_text(encoding='utf-8'))
        if data.get('dataset')!='SYNTHETIC_PIXEL_ART':
            raise RuntimeError('state root belongs to a non-demo dataset; refusing to mix training states')
    store=GameStore(state/'votes.sqlite3');store.initialize()
    app=make_app(store,state)
    logging.basicConfig(level=logging.INFO)
    should_stop=threading.Event()
    def worker_loop():
        while not should_stop.is_set():
            try:poll_once(store,Path('.'),state,args.round_seconds)
            except Exception:LOG.exception('Demo round failed; operator investigation required')
            should_stop.wait(2)
    th=threading.Thread(target=worker_loop,name='demo-worker',daemon=True)
    th.start()
    print(f'Original synthetic demo: http://127.0.0.1:{args.port}/  (NOT CIFAR-10)')
    try:uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='info')
    finally:should_stop.set();th.join(timeout=5)

if __name__=='__main__':main()
