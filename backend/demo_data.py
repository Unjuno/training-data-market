"""Deterministic, original pixel art for public-safe functional demos.

NOT CIFAR-10. Never use this data for any claim about natural image accuracy.
"""
from __future__ import annotations
import random
from functools import lru_cache
import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.utils.data import Dataset

PALETTE=['#efb47d','#e8ca70','#c5dc7e','#e8a0b5','#a6d6b9',
         '#c5a7e7','#7dcad8','#e0aa85','#78a4e6','#d3d4d3']


def pixel_art(label: int, index: int, seed: int = 20261115) -> Image.Image:
    """Create a 32px icon with controlled positional and color variation."""
    rng=random.Random(seed*7 + index*31)
    dx,dy=rng.randrange(-3,4),rng.randrange(-3,4)
    canvas=Image.new('RGB',(32,32),'#10241f')
    draw=ImageDraw.Draw(canvas)
    fg=PALETTE[label]
    def line(points,width=2):
        draw.line([(x+dx,y+dy) for x,y in points], fill=fg,width=width,joint='curve')
    def ellipse(box, fill=fg):
        x0,y0,x1,y1=box;draw.ellipse((x0+dx,y0+dy,x1+dx,y1+dy),fill=fill)
    def poly(points):draw.polygon([(x+dx,y+dy) for x,y in points],fill=fg)
    def rect(box):
        x0,y0,x1,y1=box;draw.rectangle((x0+dx,y0+dy,x1+dx,y1+dy),fill=fg)
    if label==0:  # airplane silhouette
        poly([(15,3),(18,3),(19,13),(29,17),(29,20),(19,19),(19,25),(22,27),(22,29),(16,26),(10,29),(10,27),(13,25),(13,19),(3,20),(3,17),(13,13)])
    elif label==1:  # automobile
        rect((4,15,27,23));poly([(9,15),(13,9),(22,9),(26,15)])
        ellipse((7,21,12,27),'#10241f');ellipse((21,21,26,27),'#10241f')
    elif label==2:  # bird
        poly([(3,14),(14,10),(17,15),(28,8),(23,18),(16,22),(10,18)])
        line([(17,15),(24,14)],2)
    elif label==3:  # cat
        poly([(6,8),(12,12),(20,12),(26,8),(27,21),(22,26),(10,26),(5,21)])
        ellipse((11,18,13,20),'#10241f');ellipse((20,18,22,20),'#10241f')
        line([(15,22),(17,22)],1)
    elif label==4:  # deer
        ellipse((10,12,23,26));line([(11,14),(6,4),(4,3)],2);line([(20,14),(25,4),(28,3)],2)
        line([(6,8),(3,8)],2);line([(24,8),(29,8)],2)
    elif label==5:  # dog
        ellipse((9,10,23,26));poly([(9,14),(4,12),(3,21),(11,24)])
        poly([(23,14),(28,12),(29,21),(22,24)]);ellipse((16,20,18,22),'#10241f')
    elif label==6:  # frog
        ellipse((6,13,27,27));ellipse((8,8,13,17));ellipse((21,8,26,17))
        ellipse((10,12,12,14),'#10241f');ellipse((23,12,25,14),'#10241f')
    elif label==7:  # horse
        poly([(11,4),(16,10),(22,8),(24,15),(21,27),(10,27),(8,17)])
        poly([(13,9),(9,4),(7,4),(8,15)]);ellipse((19,16,21,18),'#10241f')
    elif label==8:  # ship
        poly([(3,20),(29,20),(24,27),(9,27)]);poly([(16,4),(16,19),(27,19)])
        line([(15,5),(15,20)],2)
    else:  # truck
        rect((3,10,19,23));rect((19,15,28,23));ellipse((7,21,12,27),'#10241f')
        ellipse((22,21,27,27),'#10241f')
    # All images are generated afresh by us; never retrieved from CIFAR.
    return canvas

class SyntheticPixelArt(Dataset):
    def __init__(self, seed:int=20261115):
        self.seed=seed
        self.labels=[i%10 for i in range(1600)]
        self._cache={}
    def __len__(self):return 1600
    def __getitem__(self,index):
        if not 0<=index<len(self.labels):raise IndexError(index)
        if index not in self._cache:
            image=np.array(pixel_art(self.labels[index],index,self.seed),dtype=np.float32)
            tensor=torch.from_numpy(image.transpose(2,0,1).copy())/255
            self._cache[index]=tensor
        return self._cache[index],self.labels[index]
