"""Operator-run scheduler, isolated from public HTTP requests.

A long-running service or cron job must actually run this process. Sites is
not assumed to provide Python/PyTorch hosting or background jobs.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from backend.ml import run_locked_round
from backend.store import GameStore

LOGGER=logging.getLogger('tdm.worker')


def poll_once(store:GameStore,data_root:Path,state_root:Path,
              round_seconds:int=86400, now:float|None=None):
    now=time.time() if now is None else now
    r=store.current_round()
    if r is None:return 'UNINITIALIZED'
    if r['status']=='OPEN':
        if now-r['opened_at']<round_seconds:return 'OPEN'
        store.lock_round(r['id'])
        r=store.current_round()
    if r['status']=='LOCKED':
        return run_locked_round(data_root,state_root,r['id'])
    return r['status']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-root',type=Path,default=Path('data'))
    parser.add_argument('--state-root',type=Path,default=Path('state'))
    parser.add_argument('--round-seconds',type=int,default=86400)
    parser.add_argument('--poll-interval',type=int,default=30)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    store=GameStore(args.state_root/'votes.sqlite3');store.initialize()
    while True:
        try:
            outcome=poll_once(store,args.data_root,args.state_root,args.round_seconds)
            LOGGER.info('worker cycle completed: %s',outcome if isinstance(outcome,str) else outcome.get('round_id'))
        except Exception:
            LOGGER.exception('round processing failed; round remains LOCKED for operator investigation')
            if args.once:raise
        if args.once:break
        time.sleep(max(1,args.poll_interval))

if __name__=='__main__':main()
