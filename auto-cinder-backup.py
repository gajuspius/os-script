#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import keystoneclient.v2_0.client as ksclient
import novaclient.client as nclient
from cinderclient.v2 import client
from cinderclient import __version__ as cinder_version
from datetime import datetime

##
#Max old backup count
#
bck_max = 5
parser = argparse.ArgumentParser()

parser.add_argument('-f', action='store_false', default=False,
                    dest='boolean_switch',
                    help='Set a switch to false')

parser.add_argument('-t', action='store_true', default=False,
                    dest='boolean_switch',
                    help='Set a switch to true')

results = parser.parse_args()

def get_keystone_creds():
    try:
        d = {}
        d['version'] = "2.0"
        d['username'] = os.environ['OS_USERNAME']
        d['password'] = os.environ['OS_PASSWORD']
        d['auth_url'] = os.environ['OS_AUTH_URL']
        d['tenant_name'] = os.environ['OS_TENANT_NAME']
    except KeyError:
        print "Credentials error. Run source user-operc.sh"
        sys.exit(1)
    return d

def get_nova_creds():
    try:
        d = {}
        d['version'] = "2.0"
        d['username'] = os.environ['OS_USERNAME']
        d['api_key'] = os.environ['OS_PASSWORD']
        d['auth_url'] = os.environ['OS_AUTH_URL']
        d['project_id'] = os.environ['OS_TENANT_NAME']
    except KeyError:
        print "Credentials error. Run source user-operc.sh"
        sys.exit(1)

    return d

creds = get_keystone_creds()
keystone = ksclient.Client(**creds)

nvcreds = get_nova_creds()
nova = nclient.Client(**nvcreds)
#servers = nova.servers.list()

cicreds = get_nova_creds()
cinder = client.Client(**cicreds)
volumes = cinder.volumes.list()
backups = cinder.backups.list()

def get_volumes_list():
    uid_volume = []
    for volume in volumes:
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
    #zistim si cislo servera do ktoreho je pripojeny dany volume 
    #ak nieje pripojeny  k serveru, dam do nazvu cislo volumu
    id_serv = None
    s_name = 'volumeid-' + id_volume
    id_serv = cinder.volumes.find(id=id_volume)

    if id_serv.attachments:
        srv_name = nova.servers.find(id=id_serv.attachments[0]['server_id'])
	s_name= srv_name.name

    bck_name = "bck_" + s_name + "_" + datetime.now().strftime('%d%m%Y-%H%M%S')
    return bck_name


def main(argv):
    volumes = get_volumes_list()
   
    for volume in volumes:
	uuids_bck = get_volumes_backup_list(volume)

	for uuid_bck in uuids_bck:
	    if uuid_bck['order'] > bck_max:
	        print "bck: " + uuid_bck['created'] + " - " + str(uuid_bck['order'])
		try:
		    cinder.backups.delete(uuid_bck['id'])
		except HTTPNotFound:
		    print "No volaco neni v poradku pri mazani" + uuid_bck['id']


    	##
	# Create new backup
	b_name = get_new_backup_name(volume)

        if results.boolean_switch == True:	
	    try:
                print "Create, bck: " + b_name  + " from volid: " + volume
	        cinder.backups.create(volume_id=volume,container=None,name=b_name,description='Auto backup',incremental=False,force=True)
	    except HTTPNotFound:
	        print "Oou! exception"
	else:
            print "Test Create, bck: " + b_name  + " from volid: " + volume


if __name__ == "__main__":
    main(sys.argv)
