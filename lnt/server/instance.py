import os
import shutil
import tarfile
import tempfile
import lnt.server.config
from lnt.util import logger


class Instance(object):
    """
    Wrapper object for representing an LNT instance.
    """

    @staticmethod
    def frompath(path):
        """
        frompath(path) -> Insance

        Load an LNT instance from the given instance specifier. The instance
        path can be one of:
          * The directory containing the instance.
          * The instance config file.
          * A tarball containing an instance.
        """

        # Accept paths to config files, or to directories containing 'lnt.cfg'.
        tmpdir = None
        if os.path.isdir(path):
            config_path = os.path.join(path, 'lnt.cfg')
        elif tarfile.is_tarfile(path):
            # Accept paths to tar/tgz etc. files, which we automatically unpack
            # into a temporary directory.
            tmpdir = tempfile.mkdtemp(suffix='lnt')

            logger.info("extracting input tarfile %r to %r" % (path, tmpdir))
            tf = tarfile.open(path)
            tf.extractall(tmpdir)

            # Find the LNT instance inside the tar file. Support tarballs that
            # either contain the instance directly, or contain a single
            # subdirectory which is the instance.
            if os.path.exists(os.path.join(tmpdir, "lnt.cfg")):
                config_path = os.path.join(tmpdir, "lnt.cfg")
            else:
                filenames = os.listdir(tmpdir)
                if len(filenames) != 1:
                    raise Exception("Unable to find LNT instance "
                                    "inside tarfile")
                config_path = os.path.join(tmpdir, filenames[0], "lnt.cfg")
        else:
            config_path = path

        if not config_path or not os.path.exists(config_path):
            raise Exception("Invalid config: %r" % config_path)

        config_data = {}
        exec(open(config_path).read(), config_data)
        config = lnt.server.config.Config.from_data(config_path, config_data)

        return Instance(config_path, config, tmpdir)

    def __init__(self, config_path, config, tmpdir=None):
        self.config_path = config_path
        self.config = config
        self.tmpdir = tmpdir
        self.databases = dict()
        for name in self.config.get_database_names():
            self.databases[name] = self.config.get_database(name)

    def __del__(self):
        # If we have a temporary dir, clean it up now.
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)

    def get_database(self, name):
        return self.databases.get(name, None)
