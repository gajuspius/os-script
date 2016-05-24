#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import keystoneclient.v2_0.client as ksclient
import glanceclient.v2.client as glclient
from novaclient import client

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
glance_endpoint = keystone.service_catalog.url_for(service_type='image', endpoint_type='publicURL')
glance = glclient.Client(glance_endpoint, token=keystone.auth_token)

nvcreds = get_nova_creds()
nova = client.Client(**nvcreds)
servers = nova.servers.list()


def get_servers_list():
    uid_server = []
    for server in servers:
        uid_server.append(server.id)

    return uid_server

def get_servers_snap_list(server_uuid):
    images = glance.images.list()
 
    snaps = []
    x = 1
    for image in images:
        if image.has_key('instance_uuid') and image['instance_uuid'] == server_uuid and image.has_key('image_state'):
	    snapd = {'id':image['id'],'created':image['created_at'],'status':image['image_state'],'order':x}
	    snaps.append(snapd)
	    x = (x + 1)

    snaps.sort(key=lambda a: a['created'])
    return snaps
 


def main(argv):
    uuids = get_servers_list()

    for uuid in uuids:
	snapshots = get_servers_snap_list(uuid)
	c = len(snapshots)

	
        print "server:" +  uuid 
	for x in snapshots:
	    if x['order'] > 2:
 	        print 'Delete ' + x['id'] + ' - ' + x['created']
	
		try:
            	    glance.images.delete(x['id'])
        	except HTTPNotFound:
            	    print "Could not find image " + img
	    else:
	        print x['id'] + ' - ' + x['created']

	print "\n"
	   
    srv = nova.servers.find(id="06e7e1a5-c29a-4d30-b8b5-0c5bd8af2ee6")
    srv.create_image("snap_vm_022_05052016")
    print srv

   



if __name__ == "__main__":
    main(sys.argv)

