"""CIFAR-10 reproducible training worker.

Private checkpoint and holdout files stay on the trusted ML host. This
module intentionally never downloads images on API requests or fabricates
accuracy/loss when dataset files are missing.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import random
import tempfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader,Dataset,Subset

from backend.core import assemble_arms, select_promotion, split_ids, weakness_pair
from backend.store import GameStore,GameError

class TinyCNN(nn.Module):
    """CIFAR RGB (N,3,32,32) -> ten logits, no pretrained weights."""
    def __init__(self):
        super().__init__()
        self.net=nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
                               nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
                               nn.Flatten(),nn.Linear(32*8*8,64),nn.ReLU(),nn.Linear(64,10))
    def forward(self,images):return self.net(images)

class CombinedCIFAR(Dataset):
    def __init__(self,root:str|Path):
        from torchvision.datasets import CIFAR10
        from torchvision.transforms import ToTensor
        # Dataset is downloaded separately by an operator after reviewing usage rights.
        try:
            self.train=CIFAR10(root=str(root),train=True,download=False,transform=ToTensor())
            self.test=CIFAR10(root=str(root),train=False,download=False,transform=ToTensor())
        except RuntimeError as exc:
            raise FileNotFoundError('CIFAR-10 not installed. Explicitly download official data into --data-root first.') from exc
        self.labels=[int(y) for y in self.train.targets]+[int(y) for y in self.test.targets]
    def __len__(self):return len(self.labels)
    def __getitem__(self,idx):
        if idx<50_000:return self.train[idx]
        return self.test[idx-50_000]


def seed_all(seed:int):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.set_num_threads(max(1,min(4,torch.get_num_threads())))


def train_steps(net:nn.Module, optimizer:torch.optim.Optimizer,
                data:Dataset, ids:list[int],epochs:int=10,batch_size:int=32,seed:int=0):
    if len(set(ids))!=len(ids):raise ValueError('duplicate training image IDs')
    if not ids:raise ValueError('no training images')
    generator=torch.Generator().manual_seed(seed)
    dl=DataLoader(Subset(data,ids),batch_size=batch_size,shuffle=True,generator=generator,num_workers=0)
    net.train()
    losses=[];steps=0
    for _ in range(epochs):
        for x,y in dl:
            optimizer.zero_grad(set_to_none=True)
            logits=net(x.to(dtype=torch.float32))
            loss=F.cross_entropy(logits,y)
            if not bool(torch.isfinite(loss)):raise ArithmeticError('non-finite training loss')
            loss.backward()
            optimizer.step();steps+=1;losses.append(float(loss.detach()))
    return losses,steps


def metric_pack(logits:torch.Tensor,labels:torch.Tensor,targets:tuple[int,int]):
    if logits.ndim!=2 or logits.shape[1]!=10 or labels.ndim!=1 or labels.shape[0]!=logits.shape[0]:
        raise ValueError('expected [N,10] logits and [N] labels')
    pred=logits.argmax(dim=1)
    cells=torch.bincount(labels*10+pred,minlength=100).reshape(10,10).tolist()
    supports=[sum(row) for row in cells]
    if not all(s>0 for s in supports):raise ValueError('missing class in validation split')
    recall=[cells[i][i]/supports[i] for i in range(10)]
    target_mask=(labels==targets[0])|(labels==targets[1])
    if not bool(target_mask.any()):raise ValueError('no target samples')
    overall=float(F.cross_entropy(logits,labels))
    losses=[]
    for cls in targets:
        mask=(labels==cls)
        if not bool(mask.any()):raise ValueError('missing target class')
        losses.append(float(F.cross_entropy(logits[mask],labels[mask])))
    return {'overall_loss':overall,'target_loss':sum(losses)/2,
            'accuracy':float((labels==pred).float().mean()),
            'recall':recall,'confusion':cells,'support':supports}


def evaluate(net:nn.Module,data:Dataset,ids:list[int],targets:tuple[int,int],
             batch_size:int=128):
    net.eval();pieces=[];labels=[]
    loader=DataLoader(Subset(data,ids),batch_size=batch_size,shuffle=False,num_workers=0)
    with torch.no_grad():
        for x,y in loader:
            pieces.append(net(x.to(dtype=torch.float32)).cpu());labels.append(y.cpu())
    return metric_pack(torch.cat(pieces),torch.cat(labels),targets)


def candidate_predictions(net:nn.Module,data:Dataset,ids:list[int],batch_size:int=256):
    net.eval();out={}
    with torch.no_grad():
        for chunk_start in range(0,len(ids),batch_size):
            chunk=ids[chunk_start:chunk_start+batch_size]
            batch=DataLoader(Subset(data,chunk),batch_size=batch_size,shuffle=False,num_workers=0)
            x,y=next(iter(batch));logits=net(x.to(dtype=torch.float32))
            ce=F.cross_entropy(logits,y,reduction='none')
            predictions=logits.argmax(1)
            for i,p,l in zip(chunk,predictions.tolist(),ce.tolist()):
                out[str(i)]={'predicted':int(p),'loss':round(float(l),7)}
    return out


def atomic_json(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     suffix='.tmp',delete=False) as tmp:
        json.dump(data,tmp,ensure_ascii=False,sort_keys=True,allow_nan=False)
        temp=Path(tmp.name)
    temp.replace(path)


def atomic_checkpoint(path:Path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb',dir=path.parent,suffix='.tmp',delete=False) as tmp:
        temp=Path(tmp.name)
    try:
        torch.save(data,temp)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def prepare(data_root:Path,state_root:Path,seed:int=20261115):
    if (state_root/'manifest.json').exists():raise FileExistsError('project is already initialized')
    seed_all(seed)
    data=CombinedCIFAR(data_root)
    parts=split_ids(data.labels,seed)
    model=TinyCNN()
    optimizer=torch.optim.SGD(model.parameters(),lr=.01,momentum=.9,weight_decay=0)
    initial_losses,steps=train_steps(model,optimizer,data,parts['initial'],epochs=5,batch_size=32,seed=seed)
    confusion=evaluate(model,data,parts['public'],targets=(3,5))['confusion']
    target=weakness_pair(confusion)
    pub=evaluate(model,data,parts['public'],targets=target)
    safety=evaluate(model,data,parts['safety'],targets=target)
    manifest={'schema_version':1,'seed':seed,'splits':parts,'dataset':'CIFAR-10',
              'dataset_label_sha256':hashlib.sha256(bytes(data.labels)).hexdigest(),
              'config':{'net':'TinyCNN','lr':0.01,'momentum':0.9,'weight_decay':0,
                        'batch':32,'initial_epochs':5,'round_epochs':10},
              'environment':{'torch':torch.__version__,'python':platform.python_version(),
                             'device':'cpu','float':'float32'}}
    state_root.mkdir(parents=True,exist_ok=True)
    atomic_checkpoint(state_root/'checkpoints'/'initial.pt',
                      {'model':model.state_dict(),'optimizer':optimizer.state_dict(),'seed':seed,'steps':steps})
    atomic_json(state_root/'manifest.json',manifest)
    atomic_json(state_root/'metrics'/'initial.json',{'checkpoint':'initial','target_pair':target,'public':pub})
    atomic_json(state_root/'predictions'/'initial.json',{'checkpoint':'initial',
                     'samples':candidate_predictions(model,data,parts['candidate'])})
    store=GameStore(state_root/'votes.sqlite3');store.initialize()
    store.bootstrap_samples([(i,data.labels[i]) for i in parts['candidate']],version='cifar10-official-v1')
    store.open_round('round-0001','initial',target,seed+1)
    return {'target_pair':target,'initial_optimizer_steps':steps,
            'public_loss':pub['overall_loss'],'safety_loss':safety['overall_loss']}


def run_locked_round(data_root:Path,state_root:Path, round_id:str):
    store=GameStore(state_root/'votes.sqlite3')
    round_data=store.get_round(round_id)
    if round_data['status']!='LOCKED':raise GameError('round must be LOCKED',409)
    if not round_id.startswith('round-') or not round_id[6:].isdigit():
        raise GameError('invalid round identifier',422)
    seed=int(round_data['seed']);seed_all(seed)
    manifest=json.loads((state_root/'manifest.json').read_text())
    data=CombinedCIFAR(data_root)
    classes=store.get_classes()
    counts=store.get_counts(round_id)
    chosen=assemble_arms(classes,counts,seed)
    cp=state_root/'checkpoints'/(round_data['checkpoint']+'.pt')
    checkpoint=torch.load(cp,map_location='cpu',weights_only=True)
    targets=(round_data['target_a'],round_data['target_b'])

    base=TinyCNN();base.load_state_dict(checkpoint['model'])
    before_pub=evaluate(base,data,manifest['splits']['public'],targets)
    before_safe=evaluate(base,data,manifest['splits']['safety'],targets)
    arm_results={};arm_states={}
    for key in ('community','random'):
        model=TinyCNN();model.load_state_dict(copy.deepcopy(checkpoint['model']))
        optimizer=torch.optim.SGD(model.parameters(),lr=.01,momentum=.9,weight_decay=0)
        optimizer.load_state_dict(copy.deepcopy(checkpoint['optimizer']))
        _,steps=train_steps(model,optimizer,data,chosen[key],epochs=10,batch_size=32,seed=seed)
        if steps!=40:raise AssertionError(f'expected 40 optimizer steps, got {steps}')
        arm_results[key]={'public':evaluate(model,data,manifest['splits']['public'],targets),
                          'safety':evaluate(model,data,manifest['splits']['safety'],targets),
                          'optimizer_steps':steps}
        arm_states[key]={'model':model.state_dict(),'optimizer':optimizer.state_dict(),
                         'seed':seed,'steps':checkpoint.get('steps',0)+steps}

    promoted=select_promotion(before_safe,arm_results['community']['safety'],arm_results['random']['safety'])
    new_cp=round_id if promoted!='rollback' else round_data['checkpoint']
    if promoted!='rollback':
        atomic_checkpoint(state_root/'checkpoints'/(new_cp+'.pt'),arm_states[promoted])
    # The model to be shared is selected using only the private safety split.
    selected_model=base if promoted=='rollback' else None
    if promoted!='rollback':
        selected_model=TinyCNN()
        selected_model.load_state_dict(arm_states[promoted]['model'])
    assert selected_model is not None
    new_weakness=weakness_pair(evaluate(selected_model,data,manifest['splits']['public'],targets)['confusion'])
    next_metrics=evaluate(selected_model,data,manifest['splits']['public'],new_weakness)
    # A candidate can be reused by the random control, but only the promoted
    # shared model's training examples are retired from subsequent elections.
    consumed=(chosen[promoted] if promoted!='rollback' else [])
    remaining=sorted(set(classes).difference(consumed))
    if len(remaining)<128:raise ValueError('insufficient eligible samples for the next round')
    atomic_json(state_root/'metrics'/(new_cp+'.json'),{'checkpoint':new_cp,
                'target_pair':new_weakness,'public':next_metrics})
    atomic_json(state_root/'predictions'/(new_cp+'.json'),{'checkpoint':new_cp,
                'samples':candidate_predictions(selected_model,data,remaining)})
    next_round=f"round-{int(round_id[6:])+1:04d}"
    public_result={'status':'PUBLISHED','round_id':round_id,'target_pair':targets,
                   'has_votes':chosen['has_votes'],'voted_count':len(chosen['voted']),
                   'selected_ids':chosen['community'],'control_ids':chosen['random'],
                   'community_steps':arm_results['community']['optimizer_steps'],
                   'random_steps':arm_results['random']['optimizer_steps'],
                   'before':before_pub,
                   'community':arm_results['community']['public'],
                   'random':arm_results['random']['public'],
                   'promotion':promoted,'checkpoint':new_cp,
                   'next_round':next_round,'next_target_pair':new_weakness}
    # Make the DB transition the last operation: a crash before commit is
    # recoverable by replaying the locked experiment with the same seed.
    store.finalize_round(round_id,json.dumps(public_result,ensure_ascii=False,allow_nan=False),
                         next_round_id=next_round,next_checkpoint=new_cp,
                         next_targets=new_weakness,next_seed=seed+1,consumed_ids=consumed)
    atomic_json(state_root/'results'/f'{round_id}.json',public_result)
    return public_result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','train-round'])
    parser.add_argument('--data-root',type=Path,default=Path('data'))
    parser.add_argument('--state-root',type=Path,default=Path('state'))
    parser.add_argument('--round-id',default='round-0001')
    parser.add_argument('--seed',type=int,default=20261115)
    args=parser.parse_args()
    result=(prepare(args.data_root,args.state_root,args.seed) if args.command=='prepare'
            else run_locked_round(args.data_root,args.state_root,args.round_id))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
