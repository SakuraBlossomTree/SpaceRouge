"""Local python-for-android recipe: pygame 2.6.1 instead of p4a's default 2.1.0.

Why: p4a's built-in pygame recipe is still pygame 2.1.0, whose generated C
code only compiles on Python <= 3.10 ("fatal error: 'longintrepr.h' file not
found"), while p4a's numpy recipe needs Python >= 3.11. pygame 2.6.1 builds
on Python 3.13 (it needs Cython in the host Python - see below).

pygame 2.6's surface module also needs its SIMD blitter files listed in the
Android Setup template, otherwise the app crashes at start-up with
"cannot locate symbol alphablit_alpha_sse2_argb_surf_alpha". On ARM those
files compile to empty fallbacks, so adding them is harmless.
"""

import re

from pythonforandroid.recipes.pygame import Pygame2Recipe
from pythonforandroid.toolchain import current_directory


class PygameRecipe(Pygame2Recipe):
    version = "2.6.1"
    url = "https://github.com/pygame/pygame/archive/{version}.tar.gz"

    # pygame 2.6 generates some of its C sources with Cython during the build
    # ("You need cython"), so install it into p4a's host Python first.
    # Cython 3.0.x supports Python 3.13. (Own list, not the shared default.)
    hostpython_prerequisites = ["setuptools", "cython>=3.0.11,<3.1"]

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)          # writes the Setup file
        with current_directory(self.get_build_dir(arch.arch)):
            with open("Setup") as f:
                setup = f.read()
            extra = "src_c/simd_blitters_sse2.c src_c/simd_blitters_avx2.c"
            if "simd_blitters" not in setup:
                setup = re.sub(r"^(surface\s.*?src_c/alphablit\.c)",
                               r"\1 " + extra, setup, count=1, flags=re.M)
            with open("Setup", "w") as f:
                f.write(setup)


recipe = PygameRecipe()
