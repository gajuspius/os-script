#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import time 
import keystoneclient.v2_0.client as ksclient
import novaclient.client as nclient
from cinderclient.v2 import client
from cinderclient import __version__ as cinder_version
from datetime import datetime

##
#Max old backup count
#
try:
    os.environ['OS_MAXBACKUP']
    bck_max = os.environ['OS_MAXBACKUP']
except KeyError:
    bck_max = 5

##
#blacklist
#
try:
    os.environ['OS_BLVOLUME']
    bl = os.environ['OS_BLVOLUME']
except KeyError:
    bl = []


parser = argparse.ArgumentParser()

parser.add_argument('-f', action='store_false', default=False,
                    dest='boolean_switch',
                    help='Set a switch to false')

parser.add_argument('-t', action='store_true', default=False,
                    dest='boolean_switch',
                    help='Set a switch to true')

results = parser.parse_args()


def get_nova_creds(old=None):
    if os.environ['OS_USERNAME'] == "admin":
        print "Error: Admin credentials are not valid for backup. Use non admin credentials!!!"
        sys.exit(1)

    try:
        d = {}
        d['version'] = "2.0"
        d['username'] = os.environ['OS_USERNAME']
        d['auth_url'] = os.environ['OS_AUTH_URL']

        if not (old is None):
            d['api_key'] = os.environ['OS_PASSWORD']
            d['project_id'] = os.environ['OS_TENANT_NAME']

        else:
            d['password'] = os.environ['OS_PASSWORD']
            d['project_id'] = os.environ['OS_TENANT_ID']

    except KeyError:
        print "Credentials error. Run source user-operc.sh"
        sys.exit(1)

    return d


nvcreds = get_nova_creds()
nova = nclient.Client(**nvcreds)

cicreds = get_nova_creds(old=1)
cinder = client.Client(**cicreds)

volumes = cinder.volumes.list()
backups = cinder.backups.list()

def get_volumes_list():
    uid_volume = []
    for volume in volumes:
        if volume.id not in bl:
            uid_volume.append(volume.id)

    return uid_volume

def get_volumes_backup_list(id_volume):
    bcks = []

    x = 1
    for backup in backups:
	if backup.volume_id == id_volume:
	    bckd = {'id':backup.id,'created':backup.created_at,'status':backup.status,'order': x}
            bcks.append(bckd)
	    x = (x + 1)

    bcks.sort(key=lambda a: a['created'])
    return bcks

def get_new_backup_name(id_volume):
    id_serv = None
    s_name = 'volumeid-' + id_volume
    id_serv = cinder.volumes.find(id=id_volume)

    if id_serv.attachments:
        try:
            srv_name = nova.servers.find(id=id_serv.attachments[0]['server_id'])
        except:
            print "Skontroluj ci mas ok OS_TENANT_ID"
            sys.exit(1)
    	s_name= srv_name.name

    bck_name = "bck_" + s_name + "_" + datetime.now().strftime('%d%m%Y-%H%M%S')
    return bck_name


def main(argv):
    volumes = get_volumes_list()
    _dt = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
  
    for volume in volumes:
	uuids_bck = get_volumes_backup_list(volume)

	for uuid_bck in uuids_bck:
	    if uuid_bck['order'] > int(bck_max):
                
                if results.boolean_switch == True:
                    try:
                        print _dt + ": Delete, bck: " + uuid_bck['created']
                        cinder.backups.delete(uuid_bck['id'])
                        time.sleep(4)
                    except HTTPNotFound:
                        print "No volaco neni v poradku pri mazani" + uuid_bck['id']
                else:
                    print _dt + ": Test Delete, bck: id:" + uuid_bck['id'] + "-" + uuid_bck['created']



    	##
	# Create new backup
	b_name = get_new_backup_name(volume)


        if results.boolean_switch == True:	
            try:
                print _dt + ": Create, bck: " + b_name  + " from volid: " + volume
	        cinder.backups.create(volume_id=volume,container=None,name=b_name,description='Auto backup',incremental=False,force=True)
	    except Exception as exc:
                print exc
	else:
            print _dt + ": Test Create, bck: " + b_name  + " from volid: " + volume


if __name__ == "__main__":
    main(sys.argv)
