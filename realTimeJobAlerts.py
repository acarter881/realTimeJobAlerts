import smtplib
import os
import re
import time
import json
import sqlite3
from tqdm import tqdm
from email.message import EmailMessage
from helium import *
from bs4 import BeautifulSoup

class myWorkday:
    def __init__(self):
        self.url = 'https://REDACTED.com'
        self.jobGroupToFind = '4'
        self.workDayUser = 'REDACTED@REDACTED.com'
        self.workDayPass = os.environ.get('REDACTED_PASS')
        self.emailUser = os.environ.get('EMAIL_USER')
        self.emailPass = os.environ.get('EMAIL_PASS')
        self.jobGroupRegEx = re.compile('JG\s(\d{1}\+?).*')

    def startBrowser(self):
        self.browser = start_chrome(url=self.url, headless=True) # Create an instance of Google Chrome

        time.sleep(5)
        write(self.workDayUser)                                  # Write username

        time.sleep(1)  
        press(ENTER)                                             # Press ENTER to move to the password screen

        time.sleep(2)               
        write(self.workDayPass)                                  # Write password

        time.sleep(1)              
        press(ENTER)                                             # Press ENTER to move to the confirmation screen

        time.sleep(3)
        press(ENTER)                                             # Press ENTER to move to Workday's data

        time.sleep(5)                                            # Wait for the webpage to load

    def scrapeHTML(self):
        self.soup = BeautifulSoup(self.browser.page_source, 'html.parser')

        self.myJSON = json.loads(self.soup.body.find('pre').next)

        self.totalJobs = self.myJSON['body']['facetContainer']['paginationCount']['text']           # Total number of jobs

        self.listItems = self.myJSON['body']['children'][0]['listItems']                            # The list items

        self.rows = []

        for i in range(len(self.listItems)):
            self.ID = self.listItems[i]['subtitles'][0]['value']                                    # Job ID
            
            self.title = self.listItems[i]['title']['instances'][0]['text']                         # Job Title
            
            self.postingDate = self.listItems[i]['subtitles'][1]['value'].split(': ')[1]            # Job Posting Date
            
            self.location = self.listItems[i]['subtitles'][2]['instances'][0]['text']               # Job Location
            
            self.jobURL = self.listItems[i]['title']['selfUriTemplate']
            self.jobURL = self.jobURL[:4] + '/d' + self.jobURL[4:]
            self.jobURL = 'https://www.REDACTED.com' + self.jobURL + '.htmld'                       # Job URL
            
            self.rows.append((self.ID, self.title, self.postingDate, self.location, self.jobURL))   # Append data to list

        kill_browser()

    def toDatabase(self, pathToDatabase):
        self.database = pathToDatabase

        self.connection = sqlite3.connect(database=self.database)

        self.cursor = self.connection.cursor()

        self.jobTitles = []

        self.jobURLS = []

        # Loop through all of the rows. The database's table name is "jobs"
        for i in range(len(self.rows)):
            self.cursor.execute("SELECT * FROM jobs WHERE Job_Identifier = ?", (self.rows[i][0],))
            
            self.exists = self.cursor.fetchone()
            
            if self.exists:
                # If the job ID is in the database, skip that job id and go to the next job id
                pass       
            else:
                # If the job ID is NOT in the database, add the job's title to the jobTitles list, add the job's URL to the jobURLS list, and insert the job's details into the database's table
                self.jobTitles.append(self.rows[i][1])
                self.jobURLS.append(self.rows[i][4])
                self.cursor.execute("INSERT INTO jobs VALUES(?, ?, ?, ?, ?)", (self.rows[i][0], self.rows[i][1], self.rows[i][2], self.rows[i][3], self.rows[i][4]))

        # Commit the changes (if any) to the database's table
        self.connection.commit()

        # Close the database connection
        self.connection.close()

        if len(self.jobURLS) == 0:
            print('There are no new jobs to search for...')
        else:
            print(f'\nThere are {len(self.jobURLS)} new jobs to search for.')

    def findOurJobs(self):
        self.validTitles = []
        self.validJobs = []
        self.validLocations = []

        if len(self.jobURLS) == 0:
            pass
        else:
            for i in tqdm(range(len(self.jobURLS))):
                self.browser = start_chrome(url=self.jobURLS[i], headless=True)

                time.sleep(5)
                write(self.workDayUser)         # Write username

                time.sleep(1)  
                press(ENTER)                    # Press ENTER to move to the password screen

                time.sleep(2)               
                write(self.workDayPass)         # Write password

                time.sleep(1)              
                press(ENTER)                    # Press ENTER to move to the confirmation screen

                time.sleep(3)
                press(ENTER)                    # Press ENTER to move to Workday's data
                
                time.sleep(5)                   # Wait for the webpage to load

                self.soup = BeautifulSoup(self.browser.page_source, 'html.parser')

                self.myCLS = self.soup.find('div', {'class': 'GWTCKEditor-Disabled'})

                if self.myCLS:
                    for thing in self.myCLS:
                        try:
                            if thing.startswith('JG'):
                                jg = thing
                        except Exception as e:
                            pass
                else:
                    pass

                self.jobGroup = re.search(self.jobGroupRegEx, jg).group(1)

                try:
                    self.location = self.soup.find(id='promptOption-gwt-uid-8').text
                except Exception as e:
                    self.location = 'Could not find the location in the HTML.'
            
                print(f'\nThe Job Group for {self.jobTitles[i]} is {self.jobGroup}.')

                if self.jobGroup == self.jobGroupToFind:
                    self.validTitles.append(self.jobTitles[i])
                    self.validLocations.append(self.location)
                    self.validJobs.append(self.jobURLS[i])
                else:
                    pass
                
                kill_browser()
            
            print(f'\nThere are {len(self.validJobs)} jobs matching your job group criterion.')

    def sendTheMail(self):
        if len(self.validJobs) == 0:
            # Do nothing
            pass
        else:
            # Send the email
            with smtplib.SMTP_SSL(host='smtp.gmail.com', port=465) as smtp:
                for i in range(len(self.validJobs)):
                    # Build the email message
                    self.msg = EmailMessage()
                    self.msg['Subject'] = 'A New Job Has Been Found!'
                    self.msg['From'] = self.emailUser
                    self.msg['To'] = self.workDayUser
                    self.msg.set_content(f"""\
                    The job title: {self.validTitles[i]}\n
                    The job location: {self.validLocations[i]}\n
                    The job URL: {self.validJobs[i]}\n
                    ***This message is sent from Python***
                    """)
                    self.msg.add_alternative(f"""\
                    <!DOCTYPE html>
                    <html>
                        <body>
                            <h1 style="color:red;"> Title: {self.validTitles[i]}</h1>
                            <h1 style="color:blue;"> Location: {self.validLocations[i]}</h1>
                            <h2 style="color:green;"> URL: {self.validJobs[i]}</h2>
                            <p style="color:Black;"> This message is sent from Python</p>
                            <img src="C:\\Users\\REDACTED\\Desktop\\Documents\\Miscellaneous\\python-logo-master-v3-TM.png" alt="Python Programming" width="601" height="203">
                        </body>
                    </html>
                    """, subtype='html')

                    # Log in and send the message
                    smtp.login(user=self.emailUser, password=self.emailPass)
                    smtp.send_message(msg=self.msg)
                    print(f'\nSent an email at {time.strftime("%I:%M:%S")}')

# Create a variable that will keep track of how many runs are done in a session
runs = 1

# Create the class and run the functions
while True:
    print(f'\nGoing on run number: {runs}')
    WORKDAY = myWorkday()
    WORKDAY.startBrowser()
    WORKDAY.scrapeHTML()
    WORKDAY.toDatabase(r'C:\Users\REDACTED\myIPYNBs\REDACTED.db')
    WORKDAY.findOurJobs()
    WORKDAY.sendTheMail() 
    runs += 1            # Increment the run count by 1
    time.sleep(200)      # Amount of time (in seconds) to wait between runs
