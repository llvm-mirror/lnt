"""
LNT Config object for tracking user-configurable installation parameters.
"""

import os
import re
import tempfile

import lnt.server.db.v4db


class EmailConfig:
    @staticmethod
    def from_data(data):
        # The email to field can either be a string, or a list of tuples of
        # the form [(accept-regexp-pattern, to-address)].
        to_address = data.get('to')
        if not isinstance(to_address, str):
            to_address = [(str(a), str(b)) for a, b in to_address]
        return EmailConfig(bool(data.get('enabled')), str(data.get('host')),
                           str(data.get('from')), to_address)

    def __init__(self, enabled, host, from_address, to_address):
        self.enabled = enabled
        self.host = host
        self.from_address = from_address
        self.to_address = to_address

    def get_to_address(self, machine_name):
        # The email to_address field can either be a string, or a list of
        # tuples of the form [(accept-regexp-pattern, to-address)].
        if isinstance(self.to_address, str):
            return self.to_address

        for pattern, address in self.to_address:
            if re.match(pattern, machine_name):
                return address


class DBInfo:
    @staticmethod
    def from_data(baseDir, config_data, default_email_config,
                  default_baseline_revision):
        dbPath = config_data.get('path')

        # If the path does not contain a database specifier, assume it is a
        # relative path.
        if '://' not in dbPath:
            dbPath = os.path.join(baseDir, dbPath)

        # If the path contains a relative SQLite specifier, make it absolute
        # relative to the base dir.
        if dbPath.startswith("sqlite:///") and not \
                dbPath.startswith("sqlite:////"):
            dbPath = "sqlite:///%s" % os.path.join(baseDir,
                                                   dbPath[len("sqlite:///"):])

        # Support per-database email configurations.
        email_config = default_email_config
        if 'emailer' in config_data:
            email_config = EmailConfig.from_data(config_data['emailer'])

        baseline_revision = config_data.get('baseline_revision',
                                            default_baseline_revision)
        db_version = config_data.get('db_version', '0.4')
        if db_version != '0.4':
            raise NotImplementedError("unable to load version %r database" % (
                                      db_version))

        return DBInfo(dbPath,
                      config_data.get('shadow_import', None),
                      email_config,
                      baseline_revision)

    @staticmethod
    def dummy_instance():
        return DBInfo("sqlite:///:memory:", None,
                      EmailConfig(False, '', '', []), 0)

    def __init__(self, path, shadow_import, email_config, baseline_revision):
        self.config = None
        self.path = path
        self.shadow_import = shadow_import
        self.email_config = email_config
        self.baseline_revision = baseline_revision

    def __str__(self):
        return "DBInfo(" + self.path + ")"


class Config:
    @staticmethod
    def from_data(path, data):
        # Paths are resolved relative to the absolute real path of the
        # config file.
        baseDir = os.path.dirname(os.path.abspath(path))

        # Get the default email config.
        emailer = data.get('nt_emailer')
        if emailer:
            default_email_config = EmailConfig.from_data(emailer)
        else:
            default_email_config = EmailConfig(False, '', '', [])

        dbDir = data.get('db_dir', '.')
        profileDir = data.get('profile_dir', 'data/profiles')
        schemasDir = os.path.join(baseDir, 'schemas')
        # If the path does not contain database type, assume relative path.
        dbDirPath = dbDir if "://" in dbDir else os.path.join(baseDir, dbDir)

        # FIXME: Remove this default.
        tempDir = data.get('tmp_dir', 'viewer/resources/graphs')
        blacklist = data.get('blacklist', None)
        api_auth_token = data.get('api_auth_token', None)
        if blacklist and baseDir:
            blacklist = os.path.join(baseDir, blacklist)
        else:
            blacklist = None
        secretKey = data.get('secret_key', None)

        return Config(data.get('name', 'LNT'), data['zorgURL'],
                      dbDir, os.path.join(baseDir, tempDir),
                      os.path.join(baseDir, profileDir), secretKey,
                      dict([(k, DBInfo.from_data(dbDirPath, v,
                                                 default_email_config,
                                                 0))
                           for k, v in data['databases'].items()]),
                      blacklist, schemasDir, api_auth_token)

    @staticmethod
    def dummy_instance():
        baseDir = tempfile.mkdtemp()
        dbDir = '.'
        profileDirPath = os.path.join(baseDir, 'profiles')
        tempDir = os.path.join(baseDir, 'tmp')
        schemasDir = os.path.join(baseDir, 'schemas')
        secretKey = None
        dbInfo = {'dummy': DBInfo.dummy_instance()}
        blacklist = None

        return Config('LNT',
                      'http://localhost:8000',
                      dbDir,
                      tempDir,
                      profileDirPath,
                      secretKey,
                      dbInfo,
                      blacklist,
                      schemasDir,
                      "test_key")

    def __init__(self,
                 name,
                 zorgURL,
                 dbDir,
                 tempDir,
                 profileDir,
                 secretKey,
                 databases,
                 blacklist,
                 schemasDir,
                 api_auth_token=None):
        self.name = name
        self.zorgURL = zorgURL
        self.dbDir = dbDir
        self.tempDir = tempDir
        self.secretKey = secretKey
        self.blacklist = blacklist
        self.profileDir = profileDir
        self.schemasDir = schemasDir
        while self.zorgURL.endswith('/'):
            self.zorgURL = zorgURL[:-1]
        self.databases = databases
        for db in self.databases.values():
            db.config = self
        self.api_auth_token = api_auth_token

    def get_database(self, name):
        """
        get_database(name) -> db or None

        Return the appropriate instance of the database with the given name, or
        None if there is no database with that name."""

        # Get the database entry.
        db_entry = self.databases.get(name)
        if db_entry is None:
            return None

        return lnt.server.db.v4db.V4DB(db_entry.path, self,
                                       db_entry.baseline_revision)

    def get_database_names(self):
        return list(self.databases.keys())
