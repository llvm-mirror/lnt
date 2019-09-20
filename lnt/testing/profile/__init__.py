# This is the profile implementation registry. Register new profile
# implementations here.

from __future__ import absolute_import
from .profilev1impl import ProfileV1
from .profilev2impl import ProfileV2
from .perf import LinuxPerfProfile
IMPLEMENTATIONS = {0: LinuxPerfProfile, 1: ProfileV1, 2: ProfileV2}
