#!/usr/bin/env python
# encoding: utf-8

import numpy
import pylab
import json
import math

def plotlinklengths(nets, title, size, filepath=None):
  pylab.clf()
  pylab.figure(figsize=(16,9))
  for net in nets:
      lengths = []
      for _node in net:
        node = float(_node)
        for link in net[_node]:
          lengths.append(min(abs(link - node), abs(link - node - 1), abs(link - node + 1)))
      pylab.plot(sorted(lengths), numpy.arange(len(lengths))/float(len(lengths)), linewidth=4)
  pylab.xscale("log")
  pylab.xlabel("link length")
  pylab.ylabel("fraction of links with this length or less")
  pylab.title(title)
  pylab.xlim(1./(size**2), 0.5)
  if filepath:
    pylab.savefig(filepath)
  else:
    pylab.show()


def plotring(locs, paths, title, filepath=None):
  pylab.clf()
  pylab.figure(figsize=(12,9))
  locs = numpy.array(locs)
  ringx = numpy.sin(locs*math.pi*2)
  ringy = numpy.cos(locs*math.pi*2)
  pylab.scatter(ringx, ringy)# , color=matplotlib.cm.spectral(locs))
  maxpathlen = max([len(path) for path in paths])
  for path in paths:
      path = numpy.array(path)
      pathx = numpy.sin(path*math.pi*2)
      pathy = numpy.cos(path*math.pi*2)
      for n,x in enumerate(pathx):
        try:
          xp1 = pathx[n+1]
          y = pathy[n]
          yp1 = pathy[n+1]
          color = matplotlib.cm.spectral(float(len(path)) / maxpathlen)
        except:
          break
        # pylab.plot([x, xp1], [y, yp1])# , color=color)
      pylab.plot(pathx, pathy, linewidth=2)# , color=color)
  pylab.title(title)
  if filepath:
    pylab.savefig(filepath)
  else:
    pylab.show()

with open("routingsim_results.json") as f:
    result = json.load(f)

params = result["_params"]
plotlinklengths(result["random"]["nets"]+result["smallworldindex"]["nets"]+result["smallworldapprox"]["nets"]+result["smallworldapproxnonuniform"]["nets"]+result["kleinberg"]["nets"], 
                "Link lengths", 
                filepath="size-{}-peers-{}-backoffpercentage-{:03}-hash-{}-linklengths-random-index-kleinberg-approx-nonuniform.png".format(
                  len(params["locs"]), 
                  params["outdegree"], 
                  int(100*params["backoffprobability"]), 
                  hash(tuple(params["locs"]))),
                size=params["size"])
plotlinklengths(result["smallworlddistance"]["nets"]+result["smallworldreject"]["nets"]+result["smallworlddistancenonuniform"]["nets"], 
                "Link lengths", 
                filepath="size-{}-peers-{}-backoffpercentage-{:03}-hash-{}-linklengths-distance-distancenonuniform-reject.png".format(
                  len(params["locs"]), 
                  params["outdegree"], 
                  int(100*params["backoffprobability"]), 
                  hash(tuple(params["locs"]))),
                size=params["size"])
for name, title in [
    ("smallworldapprox", "small world paths approximated optimization"),
    ("smallworldapproxnonuniform", "small world paths approximated optimization, nonuniform"),
    ("smallworldindex", "small world paths optimized by index"),
    ("smallworlddistance", "small world paths optimized by distance"),
    ("smallworlddistancenonuniform", "small world paths optimized by distance, nonuniform"),
    ("smallworldreject", "small world paths optimized by rejection"),
    ("kleinberg", "kleinberg paths"),
    ("random", "random paths"),
    ]:
  if result[name]["paths"]:
    plotring(params["locs"], result[name]["paths"], title, 
             filepath="size-{}-peers-{}-backoffpercentage-{:03}-hash-{}-meanlen-{}-{}.png".format(
               len(params["locs"]), 
               params["outdegree"], 
               int(100*params["backoffprobability"]), 
               hash(tuple(params["locs"])), 
               int(numpy.mean(result[name]["pathlengths"])),
               name))
