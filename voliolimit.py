#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import time
import sys
import argparse
import libvirt
from distutils.version import LooseVersion
from urlparse import urlparse

from cinderclient import client
from cinderclient import __version__ as cinder_version

from novaclient import client as novacl
#from novaclient import __version__ as novacl_version

__version__ = '0.1'

##  Set storages name example:
#__storages__ = {'@iscsi-01-vnet.in','@iscsi-01-nay.in'}
#
__storages__ = {'@iscsi-01-vnet.in'}


ALL = 'allservers'
SERVER = 'server'

_IOBYTES=12582912
_IOIOPS=200


_LI = _LW = _LE = _LC = _LX = None
DEFAULT_LOG_LEVEL = logging.INFO

def get_arg_parser():

    class MyParser(argparse.ArgumentParser):
        def error(self, message):
            self.print_help()
            sys.stderr.write('\nerror: %s\n' % message)
            sys.exit(2)

    general_description = ("Runtime change disk iolimit management tool\n\n"
                           "This is a helper for OpenStack's runtime change disk iolimit functionality to help \n\n")

    general_epilog = (
            "Use {action} -h to see specific action help\n\n"
            "*Basic usage:*\n"
            "Change iolimits for all servers witch use volume disk "
            ":\n"
            "\tvoliolimit.py -a allservers \n"
            )

    parser = MyParser(description=general_description,
                      epilog=general_epilog, version=__version__,
                      add_help=True,
                      formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-a', '--all-tenants', dest='all_tenants',
                        action='store_true', default=False,
                        help='include volumes from all tenants')

    parser.add_argument('--os-username', metavar='<auth-user-name>',
                        dest='username',
                        default=os.environ.get('OS_USERNAME', ''),
                        help='OpenStack user name. Default=env[OS_USERNAME]')

    parser.add_argument('--os-password', metavar='<auth-password>',
                        dest='password',
                        default=os.environ.get('OS_PASSWORD', ''),
                        help='Password for OpenStack user. '
                        'Default=env[OS_PASSWORD]')

    parser.add_argument('--os-tenant-name', metavar='<auth-tenant-name>',
                        dest='tenant_name',
                        default=os.environ.get('OS_TENANT_NAME', ''),
                        help='Tenant name. Default=env[OS_TENANT_NAME]')

    parser.add_argument('--os-auth-url', metavar='<auth-url>', dest='auth_url',
                        default=os.environ.get('OS_AUTH_URL', ''),
                        help='URL for the authentication service. '
                        'Default=env[OS_AUTH_URL]')

    parser.add_argument('--os-tenant-id', metavar='<auth-tenant-id>', dest='tenant_id',
                        default=os.environ.get('OS_TENANT_ID', ''),
                        help='Tenant id. Default=env[OS_TENANT_ID]')

    parser.add_argument('-q', '--quiet', dest='quiet',
                        default=False, action='store_true',
                        help='No output except warnings or error')

    subparsers = parser.add_subparsers(title='actions', dest='action',
                                       help='action to perform')

    typevolume = dict(dest='t_volume', default='std',
                      metavar='<#>',
                      type=str, help="Type of volume. Available "
                      "values are: std, pro, flash. Default value is std")

    iobytes = dict(dest='io_bytes',default=_IOBYTES,
                   metavar='<#>',
                   type=int, help='Set disk bytes sec. limit. Default value is 6291456')

    ioiops = dict(dest='io_iops', default=_IOIOPS,
                 metavar='<#>',
                 type=int, help='Set disk ips sec. limit. Default value is 150')


    # ALL action
    parser_all = subparsers.add_parser(ALL, help='do all server from tenant')
    parser_all.add_argument('--type-volume', **typevolume)
    parser_all.add_argument('--io-bytes', **iobytes)
    parser_all.add_argument('--io-iops', **ioiops)

    # Server parser
    parser_server = subparsers.add_parser(SERVER, help='do server')
    parser_server.add_argument('--type-volume', **typevolume)
    parser_server.add_argument('--io-bytes', **iobytes)
    parser_server.add_argument('--io-iops', **ioiops)

    return parser


def create_logger(quiet=False):
    global _LI, _LW, _LE, _LC, _LX

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.WARNING if quiet else DEFAULT_LOG_LEVEL)

    ch = logging.StreamHandler()
    ch.setLevel(DEFAULT_LOG_LEVEL)


    formatter = logging.Formatter(time.strftime("%Y-%m-%d %H:%M:%S") + ': %(levelname)s: %(message)s')
    ch.setFormatter(formatter)

    logger.addHandler(ch)
    _LI = logger.info
    _LW = logger.warning
    _LE = logger.error
    _LC = logger.critical
    _LX = logger.exception

    return logger

class IOLimitServiceException(Exception):
    def __init__(self, what, *args, **kwargs):
        super(IOLimitServiceException, self).__init__(*args, **kwargs)
        self.what = what

    def __str__(self):
        return u'%s: %s' % (self.__class__.__name__, self.what)

class IOLimitIsDown(IOLimitServiceException):
    pass

class IOLimitService(object):

    WANT_V = '1.1.1'
    HAS_SEARCH_OPTS = LooseVersion(cinder_version) >= LooseVersion(WANT_V)

    def __init__(self, username, api_key, project_id, auth_url, tenant_id,
                 poll_delay=None):
        super(IOLimitService, self).__init__()
        self.username = username
        self.api_key = api_key
        self.project_id = project_id
        self.auth_url = auth_url
        self.iobytes = 0
        self.ioiops = 0

        # Some functionality requires API version 2
        self.client = client.Client(version=2.0,
                username=username,
                api_key=api_key,
                project_id=project_id,
                auth_url=auth_url,
                tenant_id=tenant_id)

        # Nova API
        self.novacl = novacl.Client(version=2.0,
                username=username,
                password=api_key,
                project_id=tenant_id,
                auth_url=self._change_authurlVersion(auth_url, path='/v2.0'))

        self.status_msg = ''
        if not self.HAS_SEARCH_OPTS:
            _LW('--all-tenants disabled, need cinderclient v%s', self.WANT_V)

    @property
    def iolimit_status(self):
         """On error this may have additional information."""
         return self.status_msg

    @property
    def is_up(self):
        try:
            services = self.client.services.list()
        # If policy doesn't allow us to check we'll have to assume it's there
        except client.exceptions.Forbidden:
            return True

        for storage in __storages__:
            for service in services:
                if service.binary == 'cinder-volume' and service.host.find(storage) != -1:
                    if service.state != 'up':
                        self.status_msg = service.state
                        return False
                    if service.status != 'enabled' and service.host.find(storage) != -1:
                        self.status_msg = service.status
                        if service.disabled_reason:
                            self.status_msg += ' (%s)' % service.disabled_reason
                        return False
        return True

        self.status_msg = "Not loaded"
        return False

    # if must be auth_url in version 2.0
    def _change_authurlVersion(self, aurl, path='/v3'):
        o_url = urlparse(aurl)
        ch_url = o_url.scheme +'://'+ o_url.netloc + path

        return ch_url

    def _set_device_name(self, device):
        a,b,c = device.split('/')
        return c

    def _list_arguments(self, all_tenants):
        if self.HAS_SEARCH_OPTS:
            return {'search_opts': {'all_tenants': all_tenants}}

        return {}

    def _search_typelist(self, t_volume='STD'):
        typenames = []
        typenames = self.client.volume_types.list()

        for typename in typenames:
            if typename.name.find(t_volume.upper()) != -1:
                return typename.name

        _LE('Storage name for value --type-volume=%s, doesnt exist', t_volume)
        exit(1)

    def volumes_all(self, all_tenants=True, t_volume='STD', iobytes=62914560, ioiops=150):
        """ List of volumes.
        :all_tenants: volumes for all tenants, not only ourselves
        :typevolume: type of volume (STD, PRO, FLASH)
        :iobytes: limit, bytes per seconds
        :ioiops: limit, iops per seconds

        """
        self.iobytes = iobytes
        self.ioiops = ioiops
        volumes = []
        failed = []
        servers = []

        # Check, if storage type exist
        storage_name = self._search_typelist(t_volume)

        # Get visible volumes
        volumes = self.client.volumes.list(**self._list_arguments(all_tenants))


        _LI('Starting search volumes in storage %s', storage_name)
        for vol in volumes:
            if vol.volume_type == storage_name and vol.status == 'in-use':

                # select attached servers
                for server in vol.attachments:
                    servers.append(server)
                    #_LI('Server: %s, %s', server['server_id'], server['device'])


        datas = self._get_libvirtdata(servers)
        for data in datas:
            _LI('Seting IOlimit for server %s on node: %s', data['name'], data['hypervisor'])
            failed = self._set_iolimits(data)


        _LI('Already finished.')
        return (servers, failed)

    def _set_iolimits(self,data):
        libvirtdata = data
        uri = "qemu+ssh://nova@" + libvirtdata['hypervisor'] + "/system"
        dev = str(self._set_device_name(libvirtdata['device']))

        conn = libvirt.open(uri)

        if conn == None:
            _LE('Failed to open connection on hypervizor %s', libvirtdata['hypervizor'])
            return False

        try:
            domx = conn.lookupByName(libvirtdata['kvm_name'])
        except:
            _LE('Failed to find the domain %s', libvirtdata['kvm_name'] )
            return False

        try:
            domx.setBlockIoTune(dev, {'read_bytes_sec': 0L,
                                                   'read_bytes_sec_max': 0L,
                                                   'read_iops_sec': 0L,
                                                   'read_iops_sec_max': 0L,
                                                   'size_iops_sec': 0L,
                                                   'total_bytes_sec': self.iobytes,
                                                   'total_bytes_sec_max': self.iobytes,
                                                   'total_iops_sec': self.ioiops,
                                                   'total_iops_sec_max': self.ioiops,
                                                   'write_bytes_sec': 0L,
                                                   'write_bytes_sec_max': 0L,
                                                   'write_iops_sec': 0L,
                                                   'write_iops_sec_max': 0L})
        except:
            _LE('Failed to set iolimits for %s, %s', libvirtdata['kvm_name'], dev )
            return False


        conn.close()
        return True

    # Data which need for libvirtd
    def _get_libvirtdata(self, servers):

        libvirt_data = []

        for server in servers:
            hypervs = self.novacl.servers.get(server['server_id'])
            try:
                server['hypervisor'] = getattr(hypervs, 'OS-EXT-SRV-ATTR:hypervisor_hostname')
                server['kvm_name'] =  getattr(hypervs, 'OS-EXT-SRV-ATTR:instance_name')
                server['name'] = hypervs.name
                libvirt_data.append(server)
            except:
                _LE('%s user, dont have admin credential', self.username)

        return libvirt_data


def main(args):
    iolimit = IOLimitService(username=args.username,
                             api_key=args.password,
                             project_id=args.tenant_name,
                             auth_url=args.auth_url,
                             tenant_id=args.tenant_id)
    if not iolimit.is_up:
        _LC('Cinder volume is ' + iolimit.iolimit_status)
        exit(1)

    if args.action == ALL:
        failed = True
        try:
            __, failed = iolimit.volumes_all(all_tenants=args.all_tenants,
                                             t_volume=args.t_volume,
                                             iobytes=args.io_bytes,
                                             ioiops=args.io_iops)
        except IOLimitIsDown:
            _LC('Cinder services is ' + iolimit.iolimit_status)

        if failed:
            exit(1)

    elif args.action == SERVER:
        pass

if __name__ == "__main__":
    parser = get_arg_parser()
    args = parser.parse_args()
    __ = create_logger(quiet=args.quiet)

    required = {'username': '--os-username or env[OS_USERNAME]',
                'password': '--os-password or env[OS_PASSWORD]',
                'tenant_name': '--os-tenant-name or env[OS_TENANT_NAME]',
                'auth_url': '--os-auth-url or env[OS_AUTH_URL]'}

    missing = {k: v for k, v in required.iteritems()
               if not getattr(args, k, None)}
    if missing:
        _LE('You must provide %s', ', '.join(required.itervalues()))
    else:
        main(args)


