#!/usr/bin/env pypy
# encoding: utf-8

# TODO: Simulate the effect of announcement:
# https://wiki.freenetproject.org/Announcement It works like path
# folding, but since there should not be connections to the ID
# to-be-anonunced yet, it goes the full ~18 HTL.

# Path folding only works on success, so it adds a success metric to
# the optimization. In theory it should pull the network towards a
# small world structure, but that only works when random routing is
# infeasible due to a low enough outdegree (compared with the size).

# import math
import random
import bisect
import collections
import json

# network definitions
size = 5000
outdegree = 10 # int(math.log(size, 2))*2
outdegreemax = 30 # the real outdegree is a range between min and max, excluding max
backoffprobability = 0.3 # 0.x
backoffstyle = "persistent" #: How backoff is generated. "persistent" or "probabilistic"
pathfoldpernode = 10
foafrouting = True
pathfoldminhops = 1

locs = [random.random() for i in range(size)]

def step(path, node, peers, target, maxhtl=20, foaf=None):
  """Find the best routing step from node towards target. Might require stepping back one step.

  :param path: The nodes already travelled, avoids cycles (only stepping back by at most one step).
  :param node: The current node.
  :param peers: The peers of the current node.
  :param target: The target location we want to route towards.
  :param maxhtl: The maximum path length.
  :param foaf: Whether we take the peers of peers into account for routing. Set as {peer: [peersofpeer, ...], ...}.
  """
  if path[maxhtl:]:
       e = ValueError("Reached the limit of {} steps with path to {}. Last 5 steps: {}.".format(maxhtl, target, path[-5:]))
       e.path = path
       raise e

  # depth first traversal
  p = set(path)
  untested = [peer for peer in list(peers)
              if not peer in p 
              and (backoffstyle != "probabilistic" or
                   (backoffprobability == 0.0 # optimization for common case
                    or random.random() > backoffprobability))]
  if not untested:
    if not path[:-1]:
       raise ValueError("No nodes to test and cannot step back: Cannot find a route to the target in this network.")
    # step back
    return path[-2]
  # if we’re done, be done.
  if node != target and target in untested:
    return target
  if foaf:
    options = sorted(untested, key=lambda peer: min(abs(peer - target),
                                                    min(abs(p - target)
                                                        for p in foaf[peer])))
  else:
    options = sorted(untested, key=lambda peer: abs(peer - target))
  best = options[0]
  if best == node:
    if not path[:-1]:
       raise ValueError("Cannot find a route to the target in this network.")
    best = path[-2]
  return best


def greedyrouting(net, start, target):
    path = [start]
    backedoff = {}
    # route on small world net
    while path[-1] != target:
      node = path[-1]
      peers = net[node]
      if backoffstyle == "persistent":
        if not node in backedoff:
          backedoff[node] = set([p for p in peers if random.random() < backoffprobability])
        else:
          peers = [p for p in peers if not p in backedoff[node]]
      foaf = (dict([(peer, net[peer]) for peer in peers])
              if foafrouting else None)
      path.append(step(path, node, peers, target, foaf=foaf))
    return path



def rejectbydistance(myloc, peerlocs, potentialpeer):
            """reject = 1 - min(1, d5 / d)
            with d as the distance and d5 as the distance of the node 1/5th in the order of peers."""
            dist = min(abs(potentialpeer - myloc), abs(myloc - potentialpeer))
            if not peerlocs:
              return random.random() < 0.0001/dist # want a short connection.
            pl = sorted(peerlocs)
            # the median distance
            mediandistance = pl[len(pl)//2]
            # always accept nodes which are factor 100 closer to me than the median of my connections
            d5 = mediandistance/100
            # rejectprob = random.random() < 1 - min(1, 0.5 + (0.5*d5 / dist))
            rejectprob = 1 - min(1, d5 / dist)
            return random.random() < rejectprob


def rejectbydistancesquared(myloc, peerlocs, potentialpeer):
            """reject = 1 - min(1, d5 / d)
            with d as the distance and d5 as the distance of the node 1/5th in the order of peers."""
            dist = min(abs(potentialpeer - myloc), abs(myloc - potentialpeer))
            if not peerlocs:
              return random.random() < 0.0001**2 / dist**2 # want a short connection.
            pl = sorted(peerlocs)
            # the median distance
            mediandistance = pl[len(pl)//2]
            # always accept nodes which are factor 100 closer to me than the median of my connections
            d5 = mediandistance/100
            # rejectprob = random.random() < 1 - min(1, 0.5 + (0.5*d5 / dist))
            rejectprob = 1 - min(1, d5**2 / dist**2)
            return random.random() < rejectprob


def rejectnever(myloc, peerloc, potentialpeer):
  return False


def pathfold(net, locs, numstarts=size*pathfoldpernode, numtargets=3, rejectfun=rejectnever, minhops=pathfoldminhops):
    """Simulate pathfolding.
    
    :param net: The network: {node: [peer, ...]}
    :param locs: All nodes [node, ...]
    :param numstarts: The number of times a random should be selected for path folding.
    :param numtargets: The number of targets each node which folds should use for folding. The total number of path folding tries is numstarts*numtargets.
    :param rejectfun: A function f(node, peers, target) which returns True if the folding should be rejected (not done).
    :param minhops: The minimum number of hops required to fold. Implements no-close-folding.
    """
    starts = [random.choice(locs) for i in range(numstarts)]
    success = collections.Counter()
    graceperiod = collections.Counter() # new links should only be replaced after a a given number of routing tries (equivalent to waiting some time).
    graceperiod_init = 100
    for n, start in enumerate(starts):
        import sys
        if not n%100:
          sys.stderr.write(".")
          sys.stderr.flush()
        targets = [random.choice(locs) for i in range(numtargets)]
        # paths = []
        for target in targets:
            if target == start:
                continue
            # reduce the grace period for all links
            graceperiod.subtract(graceperiod.keys())
            # purge all non-positive values
            for k,v in graceperiod.items():
              if v <= 0:
                del graceperiod[k]
            try:
                path = greedyrouting(net, start, target)
            except ValueError as e:
                print e
                continue
            # paths.append(path)
            # pathfolding
            tofold = path[minhops:]
            for n, node in enumerate(tofold):
              # count successes
              if n > 0:
                  success[(tofold[n-1], node)] += 1
              peers = net[node]
              if node == target or target in peers:
                  continue # already connected
              if not rejectfun(node, peers, target):
                bysuccesses = sorted([(success[node, peers[n]], n)
                                      for n in range(len(peers))
                                      if not graceperiod[(node, peers[n])]])
                if bysuccesses:
                  worstpeerindex = bysuccesses[0][1]
                  success[node, peers[worstpeerindex]] = 0
                  peers[worstpeerindex] = target
                  graceperiod[(node, target)] = graceperiod_init
    

def numpeers(realoutdegree=outdegree):
    """Get the target number of peers for a given node."""
    return int((float(realoutdegree) / outdegree) *
               (outdegree + random.random() *
                (outdegreemax - outdegree)))
                  

def randomlinks(locs, starts, targets, filepath=None):
    randomnet = {}
    for i in locs:
      peers = set()
      for j in range(numpeers(outdegree)):
        peer = random.choice(locs)
        while peer in peers:
            peer = random.choice(locs)
        peers.add(peer)
      randomnet[i] = list(peers)
    # add pathfolding for optimization
    pathfold(randomnet, locs)
    # route to each target
    paths = []
    for target in targets:
      for start in starts:
        try:
            paths.append(greedyrouting(randomnet, start, target))
        except ValueError as e:
            print e
            continue
    return randomnet, paths



def smallworldbydistance(locs, starts, targets, filepath=None):
    # small world routing, but with non-uniform number of links
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    for i in sortedlocs:
        smallworldnet[i] = []
    nummediumlinks = outdegree
    maxmediumdistance = lensortedlocs // 2
    for n, loc in enumerate(sortedlocs):
      for peer in range(numpeers(outdegree)):
        # FIXME: This is horribly slow.
        def chooselink(maxdist, direction=1):
          choices = range(1, maxmediumdistance + 1)
          weights = [1.0/min(abs(loc - sortedlocs[(n+c*direction)%lensortedlocs]), 
                             abs(sortedlocs[(n+c*direction)%lensortedlocs] - loc)) 
                     for c in choices]
          cumdist = []
          accumulator = 0
          for c in weights:
              accumulator += c
              cumdist.append(accumulator)
          x = random.uniform(0, cumdist[-1])
          return choices[bisect.bisect(cumdist, x)]
        down = chooselink(maxmediumdistance, direction=-1)
        up = chooselink(maxmediumdistance, direction=1)
        lower = (n-down)%lensortedlocs
        while lower in smallworldnet[loc]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = (n+up)%lensortedlocs
        while upper in smallworldnet[loc] :
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[loc].append(sortedlocs[lower])
        smallworldnet[loc].append(sortedlocs[upper])
    # add pathfolding for optimization
    pathfold(smallworldnet, locs)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths


def smallworldbyreject(locs, starts, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    for i in sortedlocs:
        smallworldnet[i] = []
    def chooselink():
          for i in range(1000):
            potentialpeer = random.choice(sortedlocs)
            while potentialpeer in smallworldnet[loc] or potentialpeer == loc:
              potentialpeer = random.choice(sortedlocs)
            if not rejectbydistance(loc, smallworldnet[loc], potentialpeer):
              return potentialpeer
          # give up after 100 tries.
          return potentialpeer
    for peer in range(numpeers(outdegree)):
      for n, loc in enumerate(sortedlocs):
        smallworldnet[loc].append(chooselink())
    # initial path folding with random targets
    # def rejectfun(*args):
    #     return False
    pathfold(smallworldnet, locs) # , rejectfun=rejectfun)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths



def smallworldbyindex(locs, starts, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    for i in sortedlocs:
        smallworldnet[i] = []
    nummediumlinks = outdegree
    maxmediumdistance = lensortedlocs // 2
    for n, loc in enumerate(sortedlocs):
      for peer in range(numpeers(outdegree)):
        def chooselink(maxdist):
          choices = range(1, maxmediumdistance + 1)
          weights = [1.0/c for c in choices]
          cumdist = []
          accumulator = 0
          for c in weights:
              accumulator += c
              cumdist.append(accumulator)
          x = random.uniform(0, cumdist[-1])
          return choices[bisect.bisect(cumdist, x)]
        down = chooselink(maxmediumdistance)
        up = chooselink(maxmediumdistance)
        lower = (n-down)%lensortedlocs
        while lower in smallworldnet[loc]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = (n+up)%lensortedlocs
        while upper in smallworldnet[loc] :
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[loc].append(sortedlocs[lower])
        smallworldnet[loc].append(sortedlocs[upper])
    # add pathfolding for optimization
    pathfold(smallworldnet, locs)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths


def smallworldapprox(locs, starts, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    linksperhop = max(1, outdegree//3)
    for i in sortedlocs:
        smallworldnet[i] = []
    # know your neighbors
    halfnumshortlinks = max(1, linksperhop/2) + 1
    maxshortdistance = outdegree/2
    for n, i in enumerate(sortedlocs):
      for dist in range(numpeers(halfnumshortlinks)):
        down = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        up = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        lower = sortedlocs[(n-down)%lensortedlocs]
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = sortedlocs[(n+up)%lensortedlocs]
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(lower)
        smallworldnet[i].append(upper)
    # long connections
    numlonglinks = linksperhop
    for n, i in enumerate(sortedlocs):
      longlinks = set()
      longlink = random.choice(sortedlocs)
      for l in range(numpeers(numlonglinks)):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for n, i in enumerate(sortedlocs):
      for l in range(numpeers(nummediumlinks)):
        def chooselink(maxdist):
          choices = range(1, maxdist + 1)
          weights = [1.0/i for i in choices]
          cumdist = []
          accumulator = 0
          for i in weights:
              accumulator += i
              cumdist.append(accumulator)
          x = random.uniform(0, cumdist[-1])
          return choices[bisect.bisect(cumdist, x)]
        down = chooselink(maxmediumdistance)
        up = chooselink(maxmediumdistance)
        lower = (n-down)%lensortedlocs
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = (n+up)%lensortedlocs
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(sortedlocs[lower])
        smallworldnet[i].append(sortedlocs[upper])
    # add pathfolding for optimization
    pathfold(smallworldnet, locs)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths


def smallworldapproxreject(locs, starts, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    linksperhop = max(1, outdegree//3)
    for i in sortedlocs:
        smallworldnet[i] = []
    # know your neighbors
    halfnumshortlinks = max(1, linksperhop/2) + 1
    maxshortdistance = outdegree/2
    for n, i in enumerate(sortedlocs):
      for dist in range(numpeers(halfnumshortlinks)):
        down = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        up = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        lower = sortedlocs[(n-down)%lensortedlocs]
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = sortedlocs[(n+up)%lensortedlocs]
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(lower)
        smallworldnet[i].append(upper)
    # long connections
    numlonglinks = linksperhop
    for n, i in enumerate(sortedlocs):
      longlinks = set()
      longlink = random.choice(sortedlocs)
      for l in range(numpeers(numlonglinks)):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for n, i in enumerate(sortedlocs):
      for i in range(numpeers(nummediumlinks)):
        def chooselink(maxdist):
          choices = range(1, maxdist + 1)
          weights = [1.0/i for i in choices]
          cumdist = []
          accumulator = 0
          for i in weights:
              accumulator += i
              cumdist.append(accumulator)
          x = random.uniform(0, cumdist[-1])
          return choices[bisect.bisect(cumdist, x)]
        down = chooselink(maxmediumdistance)
        up = chooselink(maxmediumdistance)
        lower = (n-down)%lensortedlocs
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = (n+up)%lensortedlocs
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(sortedlocs[lower])
        smallworldnet[i].append(sortedlocs[upper])
    # add pathfolding for optimization
    pathfold(smallworldnet, locs)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths


def kleinbergrouting(locs, starts, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    linksperhop = max(1, outdegree//3)
    for i in sortedlocs:
        smallworldnet[i] = []
    # know your neighbors
    halfnumshortlinks = max(1, linksperhop)
    maxshortdistance = 1
    for n, i in enumerate(sortedlocs):
      for dist in range(numpeers(halfnumshortlinks)):
        down = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        up = min([random.choice(range(maxshortdistance)) for trias in range(3)]) + 1
        lower = sortedlocs[(n-down)%lensortedlocs]
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = sortedlocs[(n+up)%lensortedlocs]
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(lower)
        smallworldnet[i].append(upper)
    # long connections
    numlonglinks = max(1, linksperhop/3)
    for n, i in enumerate(sortedlocs):
      longlinks = set()
      longlink = random.choice(sortedlocs)
      for l in range(numpeers(numlonglinks)):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for n, i in enumerate(sortedlocs):
      for i in range(numpeers(nummediumlinks)):
        down = random.choice(range(maxmediumdistance)) + 1
        up = random.choice(range(maxmediumdistance)) + 1
        lower = (n-down)%lensortedlocs
        while lower in smallworldnet[i]:
            down += 1
            lower = sortedlocs[(n-down)%lensortedlocs]
        upper = (n+up)%lensortedlocs
        while upper in smallworldnet[i]:
            up += 1
            upper = sortedlocs[(n+up)%lensortedlocs]
        smallworldnet[i].append(sortedlocs[lower])
        smallworldnet[i].append(sortedlocs[upper])
    # add pathfolding for optimization
    pathfold(smallworldnet, locs)
    # route on small world net
    paths = []
    for target in targets:
      for start in starts:
        try:
          paths.append(greedyrouting(smallworldnet, start, target))
        except ValueError as e:
          print e
        continue
    return smallworldnet, paths


randompaths = []
smallworldpaths = []
smallworldpathsindex = []
smallworldpathsreject = []
smallworldpathsdistance = []
kleinbergpaths = []
randomnets = []
smallworldnets = []
smallworldnetsindex = []
smallworldnetsreject = []
smallworldnetsdistance = []
kleinbergnets = []
for i in range(2):
    targets = [random.choice(locs) for i in range(10)]
    starts = [random.choice(locs) for i in range(10)]
    print "random"
    randomnet, randompath = randomlinks(locs, starts, targets)
    randompaths.extend(randompath)
    randomnets.append(randomnet)
    print "approx"
    smallworldnet, smallworldpath = smallworldapprox(locs, starts, targets)
    smallworldpaths.extend(smallworldpath)
    smallworldnets.append(smallworldnet)
    print "index"
    smallworldnetindex, smallworldpathindex = smallworldbyindex(locs, starts, targets)
    smallworldpathsindex.extend(smallworldpathindex)
    smallworldnetsindex.append(smallworldnetindex)
    print "reject"
    smallworldnetreject, smallworldpathreject = smallworldbyreject(locs, starts, targets)
    smallworldpathsreject.extend(smallworldpathreject)
    smallworldnetsreject.append(smallworldnetreject)
    print "distance"
    smallworldnetdistance, smallworldpathdistance = smallworldbydistance(locs, starts, targets)
    smallworldpathsdistance.extend(smallworldpathdistance)
    smallworldnetsdistance.append(smallworldnetdistance)
    print "kleinberg"
    kleinbergnet, kleinbergpath = kleinbergrouting(locs, starts, targets)
    kleinbergpaths.extend(kleinbergpath)
    kleinbergnets.append(kleinbergnet)

randompathlens = [len(p) for p in randompaths]
smallworldpathlens = [len(p) for p in smallworldpaths]
smallworldpathlensindex = [len(p) for p in smallworldpathsindex]
smallworldpathlensreject = [len(p) for p in smallworldpathsreject]
smallworldpathlensdistance = [len(p) for p in smallworldpathsdistance]
kleinbergpathlens = [len(p) for p in kleinbergpaths]

print "random:", randompathlens
print "Kleinberg:", kleinbergpathlens
print "small world:", smallworldpathlens
print "small world by index:", smallworldpathlensindex
print "small world by reject:", smallworldpathlensreject
print "small world by distance:", smallworldpathlensdistance

# store the result
result = {
  "random": {"paths": randompaths, "nets": randomnets, "pathlengths": randompathlens},
  "kleinberg": {"paths": kleinbergpaths, "nets": kleinbergnets, "pathlengths": kleinbergpathlens},
  "smallworldapprox": {"paths": smallworldpaths, "nets": smallworldnets, "pathlengths": smallworldpathlens},
  "smallworlddistance": {"paths": smallworldpathsdistance, "nets": smallworldnetsdistance, "pathlengths": smallworldpathlensdistance},
  "smallworldindex": {"paths": smallworldpathsindex, "nets": smallworldnetsindex, "pathlengths": smallworldpathlensindex},
  "smallworldreject": {"paths": smallworldpathsreject, "nets": smallworldnetsreject, "pathlengths": smallworldpathlensreject},
  "_params": {
    "outdegree": outdegree,
    "outdegreemax": outdegreemax, 
    "backoffprobability": backoffprobability,
    "backoffstyle": backoffstyle,
    "pathfoldpernode": pathfoldpernode,
    "foafrouting": foafrouting,
    "pathfoldminhops": pathfoldminhops,
    "locs": locs,
    "size": size,
    },
}
with open("routingsim_results.json", "w") as f:
  json.dump(result, f)
