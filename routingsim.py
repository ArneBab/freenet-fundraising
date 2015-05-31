
import math
import random
import bisect
import collections
import json
size = 10000
locs = [random.random() for i in range(size)]
outdegree = int(math.log(size, 2))*2
backoffprobability = 0.0 # 0.x
def step(path, node, peers, target, maxhtl=500):
  if path[maxhtl:]:
       raise ValueError("Reached the limit of {} steps with path to {}: {}.".format(maxhtl, target, path))

  # depth first traversal
  p = set(path)
  untested = [peer for peer in list(peers)
              if not peer in p 
              and (backoffprobability == 0.0 # optimization for common case
                   or random.random() > backoffprobability)]
  if not untested:
    if not path[:-1]:
       raise ValueError("No nodes to test and cannot step back: Cannot find a route to the target in this network.")
    # step back
    return path[-2]
  options = sorted(untested, key=lambda peer: abs(peer - target))
  best = options[0]
  if best == node:
    if not path[:-1]:
       raise ValueError("Cannot find a route to the target in this network.")
    best = path[-2]
  return best


def greedyrouting(net, start, target):
    path = [start]
    # route on small world net
    while path[-1] != target:
      node = path[-1]
      peers = net[node]
      path.append(step(path, node, peers, target))
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


def pathfold(net, locs, numstarts=size, numtargets=3, rejectfun=rejectnever):
    """Simulate pathfolding."""
    starts = [random.choice(locs) for i in range(numstarts)]
    success = collections.Counter()
    for n, start in enumerate(starts):
        import sys
        if not n%100:
          sys.stderr.write(".")
          sys.stderr.flush()
        targets = [random.choice(locs) for i in range(numtargets)]
        paths = []
        for target in targets:
            if target == start:
                continue
            try:
                path = greedyrouting(net, start, target)
            except ValueError as e:
                print e
                continue
            paths.append(path)
            # pathfolding
            for n, node in enumerate(path):
              if n > 0:
                  success[(path[n-1], node)] += 1
              peers = net[node]
              if node == target or target in peers:
                  continue
              if not rejectfun(node, peers, target):
                worstpeerindex = sorted([(success[node, peers[n]], n) for n in range(len(peers))])[0][1]
                success[node, peers[n]] = 0
                peers[worstpeerindex] = target
    


def randomlinks(locs, start, targets, filepath=None):
    randomnet = {}
    for i in locs:
      peers = set()
      for j in range(outdegree):
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
      try:
          paths.append(greedyrouting(randomnet, start, target))
      except ValueError as e:
          print e
          continue
    return randomnet, paths



def smallworldbydistance(locs, start, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    for i in sortedlocs:
        smallworldnet[i] = []
    nummediumlinks = outdegree
    maxmediumdistance = lensortedlocs // 2
    for peer in range(outdegree):
      for n, loc in enumerate(sortedlocs):
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
      try:
          paths.append(greedyrouting(smallworldnet, start, target))
      except ValueError as e:
          print e
          continue
    return smallworldnet, paths


def smallworldbyreject(locs, start, targets, filepath=None):
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
    for peer in range(outdegree):
      for n, loc in enumerate(sortedlocs):
        smallworldnet[loc].append(chooselink())
    # initial path folding with random targets
    # def rejectfun(*args):
    #     return False
    pathfold(smallworldnet, locs) # , rejectfun=rejectfun)
    # route on small world net
    paths = []
    for target in targets:
      try:
          paths.append(greedyrouting(smallworldnet, start, target))
      except ValueError as e:
          print e
          continue
    return smallworldnet, paths



def smallworldbyindex(locs, start, targets, filepath=None):
    # small world routing
    smallworldnet = {}
    sortedlocs = sorted(list(locs))
    lensortedlocs = len(sortedlocs)
    for i in sortedlocs:
        smallworldnet[i] = []
    nummediumlinks = outdegree
    maxmediumdistance = lensortedlocs // 2
    for peer in range(outdegree):
      for n, loc in enumerate(sortedlocs):
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
      try:
          paths.append(greedyrouting(smallworldnet, start, target))
      except ValueError as e:
          print e
          continue
    return smallworldnet, paths


def smallworldapprox(locs, start, targets, filepath=None):
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
    for dist in range(halfnumshortlinks):
      for n, i in enumerate(sortedlocs):
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
      for l in range(numlonglinks):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for i in range(nummediumlinks):
      for n, i in enumerate(sortedlocs):
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
      try:
          paths.append(greedyrouting(smallworldnet, start, target))
      except ValueError as e:
          print e
          continue
    return smallworldnet, paths


def smallworldapproxreject(locs, start, targets, filepath=None):
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
    for dist in range(halfnumshortlinks):
      for n, i in enumerate(sortedlocs):
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
      for l in range(numlonglinks):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for i in range(nummediumlinks):
      for n, i in enumerate(sortedlocs):
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
      try:
          paths.append(greedyrouting(smallworldnet, start, target))
      except ValueError as e:
          print e
          continue
    return smallworldnet, paths


def kleinbergrouting(locs, start, targets, filepath=None):
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
    for dist in range(halfnumshortlinks):
      for n, i in enumerate(sortedlocs):
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
      for l in range(numlonglinks):
        while longlink in longlinks:
          longlink = random.choice(sortedlocs)
        longlinks.add(longlink)
      smallworldnet[i].extend(list(longlinks))
    # as many medium size links as left after substracting the long and short links
    nummediumlinks = outdegree - (halfnumshortlinks*2) - numlonglinks
    maxmediumdistance = max(lensortedlocs/(outdegree*2), outdegree)
    for i in range(nummediumlinks):
      for n, i in enumerate(sortedlocs):
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
for i in range(10):
    targets = [random.choice(locs) for i in range(10)]
    start = random.choice(locs)
    randomnet, randompath = randomlinks(locs, start, targets)
    smallworldnet, smallworldpath = smallworldapprox(locs, start, targets)
    smallworldnetindex, smallworldpathindex = smallworldbyindex(locs, start, targets)
    smallworldnetreject, smallworldpathreject = smallworldbyreject(locs, start, targets)
    smallworldnetdistance, smallworldpathdistance = smallworldbydistance(locs, start, targets)
    kleinbergnet, kleinbergpath = kleinbergrouting(locs, start, targets)
    randompaths.extend(randompath)
    smallworldpaths.extend(smallworldpath)
    smallworldpathsindex.extend(smallworldpathindex)
    smallworldpathsreject.extend(smallworldpathreject)
    smallworldpathsdistance.extend(smallworldpathdistance)
    kleinbergpaths.extend(kleinbergpath)
    randomnets.append(randomnet)
    smallworldnets.append(smallworldnet)
    smallworldnetsindex.append(smallworldnetindex)
    smallworldnetsreject.append(smallworldnetreject)
    smallworldnetsdistance.append(smallworldnetdistance)
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
    "backoffprobability": backoffprobability,
    "locs": locs,
    "size": size,
    },
}
with open("routingsim_results.json", "w") as f:
  json.dump(result, f)