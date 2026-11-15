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
from backend.store import GameStore, GameError

LOGGER=logging.getLogger('tdm.worker')


def poll_once(store:GameStore,data_root:Path,state_root:Path,
              round_seconds:int=86400, now:float|None=None):
    now=time.time() if now is None else now
    r=store.current_round()
    if r is None:return 'UNINITIALIZED'
    if r['status']=='OPEN':
        deadline=r.get('closes_at') or r['opened_at']+round_seconds
        if now<deadline:return 'OPEN'
        try:
            store.lock_round(r['id'])
        except GameError as error:
            # A second scheduler may have already locked this exact batch.
            if error.status_code != 409:raise
        r=store.current_round()
    if r['status']=='LOCKED':
        token=store.claim_round(r['id'])
        if token is None:return 'TRAINING'
        return run_locked_round(data_root,state_root,r['id'],token)
    return r['status']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-root',type=Path,default=Path('data'))
    parser.add_argument('--state-root',type=Path,default=Path('state'))
    parser.add_argument('--round-seconds',type=int,default=86400)
    parser.add_argument('--poll-interval',type=int,default=30)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--recover-round',help='Operator-only: requeue a previously failed TRAINING round')
    parser.add_argument('--confirm-worker-stopped',action='store_true',
                        help='Explicitly confirm that the previous training process is stopped')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    store=GameStore(args.state_root/'votes.sqlite3');store.initialize()
    if args.recover_round:
        if not args.confirm_worker_stopped:
            parser.error('recovery requires --confirm-worker-stopped after terminating the old process')
        previous=store.get_round(args.recover_round)
        if previous['status']!='TRAINING':
            parser.error('only TRAINING rounds can be requeued')
        store.recover_training_round(args.recover_round, previous['worker_token'])
        LOGGER.warning('Operator explicitly requeued %s; the previous process MUST be stopped', args.recover_round)
        return
    while True:
        try:
            outcome=poll_once(store,args.data_root,args.state_root,args.round_seconds)
            LOGGER.info('worker cycle completed: %s',outcome if isinstance(outcome,str) else outcome.get('round_id'))
        except Exception:
            LOGGER.exception('round processing failed; TRAINING claim remains for explicit operator recovery')
            if args.once:raise
        if args.once:break
        time.sleep(max(1,args.poll_interval))

if __name__=='__main__':main()
