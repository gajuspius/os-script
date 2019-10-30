#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import time
import sys
import argparse

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from novaclient import client as  novacl
from cinderclient import client as cindercl
from neutronclient.v2_0 import client as neutroncl
from glanceclient import client as glancecl
from gnocchiclient import client as gnocchicl
from barbicanclient import client as barbicancl
from heatclient import client as heatcl
from octaviaclient.api.v2 import octavia as octaviacl
from designateclient import client as designatecl


__version__ = '0.1'

_USERS=['heat','admin','neutron','gnocchi','designate','cinder','stack_domain_admin','dispersion','octavia','keystone','barbican','swift','glance','vnet','triliovault','zabbix','ceilometer','placement','nova','chybajuciuser']
_ENDPOINTS=['placement', 'barbican', 'nova', 'heat']
_SERVICES=['nova','cinder', 'neutron', 'glance', 'gnocchi', 'barbican','heat','octavia', 'designate']

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

class CheckOsServicesException(Exception):
    def __init__(self, what, *args, **kwargs):
        super(CheckOsServicesException, self).__init__(*args, **kwargs)
        self.what = what

    def __str__(self):
        return u'%s: %s' % (self.__class__.__name__, self.what)

class CheckOsServicesDown(CheckOsServicesException):
    pass

class CheckOsServices(object):

    def __init__(self, username, api_key, project_id, auth_url, tenant_id,
                 poll_delay=None):
        super(CheckOsServices, self).__init__()
        self.username = username
        self.api_key = api_key
        self.project_id = project_id
        self.auth_url = auth_url
        self.novacl = novacl
        self.cindercl = cindercl
        self.neutroncl = neutroncl
        self.glancecl = glancecl
        self.gnocchicl = gnocchicl
        self.barbicancl = barbicancl
        self.heatcl = heatcl
        self.octaviacl = octaviacl
        self.designatecl = designatecl

        # Keystone Session
        auth = v3.Password(auth_url=auth_url,
                          	 username=username,
                          	 password=api_key,
                          	 project_name=username,
                          	 project_domain_id='default',
                          	 user_domain_id='default')

        self.sess = session.Session(auth=auth)

    def get_module(self, module, kc):
        self._NAME = None
        self.oservice = None
        if module == "name":
            self._NAME = _USERS
            return  kc.users.list()
        elif module == "service":
            self._NAME = _SERVICES
            return kc.services.list()
        else:
            _LE("Neexistujuci modul %s", module)

    def get_keystone(self, module):
	kc = client.Client(session=self.sess, endpoint_override='https://cloud-test.vnet.sk:5000/v3')
        self.kc = kc
        return self.get_module(module, kc)


    def check_users(self, module):
        kc_all = self.get_keystone(module)
        kcUsers = self._map_toList(kc_all,module)

        for user in self._NAME:
            if user not in kcUsers:
                _LI("%s chyba v zozname %s", user, module)

    def check_endpoint(self):
        for service in _SERVICES:
            self._check_endpoint(service)
        return True

    def _check_endpoint(self,service):
        kc_all = self.get_keystone('service')
        kcServices  = self._map_toList(kc_all,'id')

        for id_service in kcServices:
            _LI('Tu by som mal mat service id: %s', id_service)
        return True


    def check_api(self):
        for service in _SERVICES:
            self._check_api(service)
        return True

    def _check_api(self, service, version='2'):
        if service == 'gnocchi' or service == 'heat' :
            version = '1'
        elif service == 'barbican':
            version = 'v1'

        try:
            servicecl = service + 'cl'
            eval(servicecl).Client(version=version, session=self.sess)
            _LI('Service %s is OK', service)
        except:
            _LE('Service %s is unreachable', service)

    def _map_toList(self,ob,module):
        a = []
        for o in ob:
            a.append(getattr(o,module,None))

        return a


#
#    @property
#    def iolimit_status(self):
#         """On error this may have additional information."""
#         return self.status_msg
#
#    @property
#    def is_up(self):
#        try:
#            services = self.client.services.list()
#        # If policy doesn't allow us to check we'll have to assume it's there
#        except client.exceptions.Forbidden:
#            return True
#
#        for storage in __storages__:
#            for service in services:
#                if service.binary == 'cinder-volume' and service.host.find(storage) != -1:
#                    if service.state != 'up':
#                        self.status_msg = service.state
#                        return False
#                    if service.status != 'enabled' and service.host.find(storage) != -1:
#                        self.status_msg = service.status
#                        if service.disabled_reason:
#                            self.status_msg += ' (%s)' % service.disabled_reason
#                        return False
#        return True
#
#        self.status_msg = "Not loaded"
#        return False
#
#    # if must be auth_url in version 2.0
#    def _change_authurlVersion(self, aurl, path='/v3'):
#        o_url = urlparse(aurl)
#        ch_url = o_url.scheme +'://'+ o_url.netloc + path
#
#        return ch_url
#
#    def _set_device_name(self, device):
#        a,b,c = device.split('/')
#        return c
#
#    def _list_arguments(self, all_tenants):
#        if self.HAS_SEARCH_OPTS:
#            return {'search_opts': {'all_tenants': all_tenants}}
#
#        return {}
#
#    def _search_typelist(self, t_volume='STD'):
#        typenames = []
#        typenames = self.client.volume_types.list()
#
#        for typename in typenames:
#            if typename.name.find(t_volume.upper()) != -1:
#                return typename.name
#
#        _LE('Storage name for value --type-volume=%s, doesnt exist', t_volume)
#        exit(1)
#
#    def volumes_all(self, all_tenants=True, t_volume='STD', iobytes=62914560, ioiops=150):
#        """ List of volumes.
#        :all_tenants: volumes for all tenants, not only ourselves
#        :typevolume: type of volume (STD, PRO, FLASH)
#        :iobytes: limit, bytes per seconds
#        :ioiops: limit, iops per seconds
#
#        """
#        self.iobytes = iobytes
#        self.ioiops = ioiops
#        volumes = []
#        failed = []
#        servers = []
#
#        # Check, if storage type exist
#        storage_name = self._search_typelist(t_volume)
#
#        # Get visible volumes
#        volumes = self.client.volumes.list(**self._list_arguments(all_tenants))
#
#
#        _LI('Starting search volumes in storage %s', storage_name)
#        for vol in volumes:
#            if vol.volume_type == storage_name and vol.status == 'in-use':
#
#                # select attached servers
#                for server in vol.attachments:
#                    servers.append(server)
#                    #_LI('Server: %s, %s', server['server_id'], server['device'])
#
#
#        datas = self._get_libvirtdata(servers)
#        for data in datas:
#            _LI('Seting IOlimit for server %s on node: %s', data['name'], data['hypervisor'])
#            failed = self._set_iolimits(data)
#
#
#        _LI('Already finished.')
#        return (servers, failed)
#
#    def _set_iolimits(self,data):
#        libvirtdata = data
#        uri = "qemu+ssh://nova@" + libvirtdata['hypervisor'] + "/system"
#        dev = str(self._set_device_name(libvirtdata['device']))
#
#        conn = libvirt.open(uri)
#
#        if conn == None:
#            _LE('Failed to open connection on hypervizor %s', libvirtdata['hypervizor'])
#            return False
#
#        try:
#            domx = conn.lookupByName(libvirtdata['kvm_name'])
#        except:
#            _LE('Failed to find the domain %s', libvirtdata['kvm_name'] )
#            return False
#
#        try:
#            domx.setBlockIoTune(dev, {'read_bytes_sec': 0L,
#                                                   'read_bytes_sec_max': 0L,
#                                                   'read_iops_sec': 0L,
#                                                   'read_iops_sec_max': 0L,
#                                                   'size_iops_sec': 0L,
#                                                   'total_bytes_sec': self.iobytes,
#                                                   'total_bytes_sec_max': self.iobytes,
#                                                   'total_iops_sec': self.ioiops,
#                                                   'total_iops_sec_max': self.ioiops,
#                                                   'write_bytes_sec': 0L,
#                                                   'write_bytes_sec_max': 0L,
#                                                   'write_iops_sec': 0L,
#                                                   'write_iops_sec_max': 0L})
#        except:
#            _LE('Failed to set iolimits for %s, %s', libvirtdata['kvm_name'], dev )
#            return False
#
#
#        conn.close()
#        return True
#
#    # Data which need for libvirtd
#    def _get_libvirtdata(self, servers):
#
#        libvirt_data = []
#
#        for server in servers:
#            hypervs = self.novacl.servers.get(server['server_id'])
#            try:
#                server['hypervisor'] = getattr(hypervs, 'OS-EXT-SRV-ATTR:hypervisor_hostname')
#                server['kvm_name'] =  getattr(hypervs, 'OS-EXT-SRV-ATTR:instance_name')
#                server['name'] = hypervs.name
#                libvirt_data.append(server)
#            except:
#                _LE('%s user, dont have admin credential', self.username)
#
#        return libvirt_data
#

def main(args):
    checkOS = CheckOsServices(username=args.username,
                             api_key=args.password,
                             project_id=args.tenant_name,
                             auth_url=args.auth_url,
                             tenant_id=args.tenant_id)

    try:
        checkOS.check_users("name")
    except CheckOsServicesDown:
        _LC('Service is down')

    checkOS.check_api()

    try:
        checkOS.check_endpoint()
    except  CheckOsServicesDown:
        _LC('Service is down')

    #if not iolimit.is_up:
    #    _LC('Cinder volume is ' + iolimit.iolimit_status)
    #    exit(1)

    #if args.action == ALL:
    #    failed = True
    #    try:
    #        __, failed = iolimit.volumes_all(all_tenants=args.all_tenants,
    #                                         t_volume=args.t_volume,
    #                                         iobytes=args.io_bytes,
    #                                         ioiops=args.io_iops)
    #    except IOLimitIsDown:
    #        _LC('Cinder services is ' + iolimit.iolimit_status)
    #
    #    if failed:
    #        exit(1)

    #elif args.action == SERVER:
    #    pass

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


