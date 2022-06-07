import time
import ovirtsdk4 as sdk
import ovirtsdk4.types as types
from socket import *
from ssl import *

def print_vm_status(vmname, vms_service):
    #search VM ID by name -> get status
    status = vms_service.list(search='name={}'.format(vmname))[0].status 
    if status == types.VmStatus.UP:
        return "on"
    elif status == types.VmStatus.DOWN:
        return "off"
    else:
        return "NaN"

def set_vm_status(vmname, vmstatus, vms_service, zVirtParams):
    #check if VM is already in desired status, return result if yes
    if print_vm_status(vmname, vms_service).lower() == vmstatus.lower():
        return vmstatus
    else:
        #actual fencing 
        if print_vm_status(vmname, vms_service) in ('on', 'off'):
            vmId = vms_service.list(search='name={}'.format(vmname))[0].id
            vmService = vms_service.vm_service(vmId)
            #send request to api 
            if vmstatus == "off":
                vmService.stop()
                return "off"

            if vmstatus == "on":
                vmService.start()
                return "on"
        else:
        #return error if VM not present
            return "NaN"
        

def readConf():
    #read conf file
    paramsFile = open("/opt/zvirt/fake_ilo/fake_ilo.conf", "r")

    zVirtURL = paramsFile.readline().replace("\n","")
    zVirtUsername = paramsFile.readline().replace("\n","")
    zVirtPasswd = paramsFile.readline().replace("\n","")
    zVirtCAcrt = paramsFile.readline().replace("\n","")
    zVirtServerCRT = paramsFile.readline().replace("\n","")
    zVirtServerKEY = paramsFile.readline().replace("\n","")

    paramsFile.close()
    #prepare dict
    zVirtParams = {'URL' : '{}'.format(zVirtURL), 'User' : '{}'.format(zVirtUsername), 'Passwd' : '{}'.format(zVirtPasswd), 'CA' : '{}'.format(zVirtCAcrt), 'CRT' : '{}'.format(zVirtServerCRT), 'KEY' : '{}'.format(zVirtServerKEY)}

    return zVirtParams

def logprint(msg):
    #log
    logfile = open('/var/log/fake_ilo.log', 'a')
    logline = time.strftime("[%Y-%m-%d %H:%M:%S] - ") + msg + "\n"
    logfile.write(logline)
    logfile.close()

#define localparams

zVirtParams = readConf()

#create socket and API connection
server_socket = socket(AF_INET, SOCK_STREAM)
zVirt_connection = sdk.Connection(url='{}'.format(zVirtParams.get('URL')), username='{}'.format(zVirtParams.get('User')), password='{}'.format(zVirtParams.get('Passwd')), insecure = True)

# get the reference to the "vms" service
vms_service = zVirt_connection.system_service().vms_service() 
username = ''

#Bind to an unused port on the local machine
server_socket.bind(('',1234))

#listen for connection
server_socket.listen(1)
tls_server = wrap_socket(server_socket, server_side=True, ssl_version=PROTOCOL_SSLv23, cert_reqs=CERT_NONE, certfile='{}'.format(zVirtParams.get('CRT')), keyfile='{}'.format(zVirtParams.get('KEY')))
logprint('server started')

while True: 
#accept connection 
    main_connection, client_address = tls_server.accept()

#server is not finished
    finished = False
    emptyresponse = 0

#while not finished
    while not finished:

#send and receive data from the client socket
        data_in = main_connection.recv(1024)
        message = data_in.decode()
        
        if message == 'quit':
            finished = True
        else:
#login = VM name
            if message.find('USER_LOGIN') > 1:
                username = message.split()[3].replace('"', '')

            if message.find('xml') > 1:
                response = '<RIBCL VERSION="2.0"></RIBCL>'
                data_out = response.encode()
                main_connection.send(data_out)
#return firmware version
            if message.find('GET_FW_VERSION') > 1:
                response = '<GET_FW_VERSION\r\n FIRMWARE_VERSION="1.91"\r\n MANAGEMENT_PROCESSOR="2.22"\r\n />'
                data_out=response.encode()
                main_connection.send(data_out)
#get power status
            if message.find('GET_HOST_POWER_STATUS') > 1:
                response = 'HOST_POWER="' + print_vm_status(username, vms_service) + '"'
                logprint('received status request for ' + username + ' from ' + client_address[0] + ':' + str(client_address[1]) + ' - responding  with: ' + print_vm_status(username, vms_service))
                data_out = response.encode()
                main_connection.send(data_out)
#set power status
            if message.find('SET_HOST_POWER') > 1:
                power = message.split()[6].replace('"', '')
                response = 'HOST_POWER="' + set_vm_status(username, power, vms_service, zVirtParams) + '"'
                logprint('received fencing command for ' + username + ' from ' + client_address[0] + ':' + str(client_address[1]) + ' - requested status: ' + power + ', status after fencing is: ' + print_vm_status(username, vms_service))
                data_out = response.encode()
                main_connection.send(data_out)
#filter out the rest
            else:
                if len(message) > 0:
                    do_nothing = 0
                else:
                    emptyresponse += 1
                if emptyresponse > 30:
                    finished = True

#close the connections
main_connection.shutdown(SHUT_RDWR)
main_connection.close()
zVirt_connection.close()

#close the server socket
server_socket.shutdown(SHUT_RDWR)
server_socket.close()



#garbage 

#import os
#import requests
#head = {'Version' : '4', 'Content-type' : 'application/xml', 'Accept' : 'application/xml'}
#URL = zVirtParams.get('URL')
#session = requests.Session()
#session.auth = (zVirtParams.get('User'), zVirtParams.get('Passwd'))
#session.verify = zVirtParams.get('CA')

#zVirtURL = 'https://zvirt.info-lend/ovirt-engine/api'
#zVirtUsername = 'emuravev@internal'
#zVirtPasswd = 'Emuravev123!'
#zVirtCAcrt = '/opt/zvirt/fake_ilo/certs/ca.crt'
#zVirtServerCRT = '/opt/zvirt/fake_ilo/certs/server.crt'
#zVirtServerKEY = '/opt/zvirt/fake_ilo/certs/server.key'

#os.system("curl --cacert '{}' --user '{}:{}' --request POST --header 'Version: 4' --header 'Content-Type: application/xml' --header 'Accept: application/xml' --data '<action/>' '{}/vms/{}/stop'".format(zVirtParams.get('CA'), zVirtParams.get('User'), zVirtParams.get('Passwd'), zVirtParams.get('URL'), vmId))
#os.system("curl --cacert '{}' --user '{}:{}' --request POST --header 'Version: 4' --header 'Content-Type: application/xml' --header 'Accept: application/xml' --data '<action/>' '{}/vms/{}/start'".format(zVirtParams.get('CA'), zVirtParams.get('User'), zVirtParams.get('Passwd'), zVirtParams.get('URL'), vmId))
