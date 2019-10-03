from __future__ import absolute_import
from lnt.util import logger
from .profile import ProfileImpl
from .profilev1impl import ProfileV1

import os
import traceback

try:
    import cPerf
except Exception:
    pass


class LinuxPerfProfile(ProfileImpl):
    def __init__(self):
        pass

    @staticmethod
    def checkFile(fn):
        return open(fn, 'rb').read(8) == b'PERFILE2'

    @staticmethod
    def deserialize(f, nm='nm', objdump='objdump', propagateExceptions=False):
        f = f.name

        if os.path.getsize(f) == 0:
            # Empty file - exit early.
            return None

        try:
            data = cPerf.importPerf(f, nm, objdump)

            # Go through the data and convert counter values to percentages.
            for f in data['functions'].values():
                fc = f['counters']
                for l in f['data']:
                    for k, v in l[0].items():
                        l[0][k] = 100.0 * float(v) / fc[k]
                for k, v in fc.items():
                    fc[k] = 100.0 * v / data['counters'][k]

            return ProfileV1(data)

        except Exception:
            if propagateExceptions:
                raise
            logger.warning(traceback.format_exc())
            return None
