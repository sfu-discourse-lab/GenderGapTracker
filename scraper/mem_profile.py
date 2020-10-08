####### Warning this code is not advised to be moved to a public repository ########

# coding: utf-8

# In[1]:
import json
import datetime
import re
import subprocess
import json

from pymongo import MongoClient
connection = MongoClient('localhost', 27017)


class collection():
    def __init__(self, size):
        self.size = size

    def __enter__(self):
        with open("article.json", 'r') as f:
            data = json.load(f)
        data["publishedAt"] = datetime.datetime.now()        
        data["lastModified"] = datetime.datetime.now()
        collection = connection["mediaTrackerM"]["media"]
        data["body"] = data["body"] + data["body"] + data["body"] + data["body"] + data["body"]
        if len(data["body"]) < self.size:
            print("Max len reached: ", len(data["body"]))
        data["body"] = data["body"][0:self.size]            
        collection.insert(data)
        self.collection = collection
        return collection

    def __exit__(self, type, value, traceback):
        #self.collection.drop()
        pass


def time_command(cmd):
    cmds = [["cd", "/g-tracker/WomenInMedia"]]
    cmds.append(cmd)

    proc = subprocess.Popen("/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                            stdin=subprocess.PIPE, shell=True)
    command = ""
    for cmd in cmds:
        command += " ".join(cmd) + ";"
    (out, error) = proc.communicate(command.encode())
    # print("Out: ", out.decode())
    # print("Error: ", error.decode())
    status = str(list(filter(lambda l: "Exit status" in l, error.decode().split('\n'))))
    memory = str(list(filter(lambda l: "Maximum resident set size" in l, error.decode().split('\n'))))
    time = str(list(filter(lambda l: "Elapsed (wall clock) time " in l, error.decode().split('\n'))))
    time = (time.replace("\\tElapsed (wall clock) time (h:mm:ss or m:ss): ", "")
               .replace("['","")
               .replace("']",""))
    memory = int(memory.replace("\\tMaximum resident set size (kbytes): ", "")
                       .replace("['","")
                       .replace("']",""))
    status = re.sub("\D", "", status)
    print("Status: ", status, " Memory: ", memory, " Time: ", time)    
    ret = {"status": status, "memory": memory, "time": time}
    return ret



cmd_quote = ["/usr/bin/time", "--verbose", 
           "../GRIM-3/bin/python", 
           "src/main/database_manipulation/quote_extractor.py", 
           "-s localhost", 
           "--db=mediaTrackerM", 
           "--col=media", 
           "--limit=0"]
cmd_gender = ["/usr/bin/time", "--verbose", 
           "../GRIM-3/bin/python", 
           "src/main/database_manipulation/entity_gender_annotator.py", 
           "-s localhost", 
           "--db=mediaTrackerM", 
           "--col=media", 
           "--limit=0",
           "--gr-ip=localhost",
           "--gr-port=5000"]
result = {}
step = 5000
for i in range(0, 100000, step):
    print("--------- Timming - Len: ", i, "---------------")
    with collection(i) as c:  
        print("Quote Extractor")
        result["Q" + str(i)] = time_command(cmd_quote)
        print("Gender annotator")
        result["G" + str(i)] = time_command(cmd_gender)
        json.dump(result, open("results.json", 'w'))


#time1 = str(time)
#time1 = time1.replace("\\tElapsed (wall clock) time (h:mm:ss or m:ss): ", "")
#print(time)
#print(time1)

#print(list(status))
#print(list(memory))

#with collection(i) as c:  
#    c.drop()

