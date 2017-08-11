# Various python script for openstack

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.


## auto-cinder-backup.pl

usage example (crontab):
`30 23 * * * cd /home/os-script/ ; . ../tenant-openrc.sh && ./auto-cinder-backup.py -t >> /var/log/tenant-backup 2>&1`

tenant-openrc.sh example:

```
export OS_PROJECT_DOMAIN_ID=default
export OS_USER_DOMAIN_ID=default
export OS_PROJECT_NAME=<tenant>
export OS_TENANT_NAME=<tenant>
export OS_USERNAME=<user>
export OS_PASSWORD=<user_pass>
export OS_AUTH_URL=http://os.example.com:5000/v2.0
export OS_IDENTITY_API_VERSION=2
export OS_IMAGE_API_VERSION=2
export OS_TENANT_ID='<tenant_id>'
export OS_MAXBACKUP=2
```

`auto-cinder-backup.pl` without -t (true) will only print debug messages without creating or deleting backups.


