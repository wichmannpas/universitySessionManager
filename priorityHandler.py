import sqlite3
import itertools
import json


class priorityHandler():
    database = sqlite3.connect('tmp.db')  # ':memory:')
    cursor = database.cursor()
    modules = []

    def __init__(self, configuration):
        self.populateDb()

        # fill tables with modules from configuration
        self.populateTables(configuration)

        self.generateAllPossibleCombinations()

    def populateDb(self):
        self.cursor.execute('''CREATE TABLE modules
                       (moduleId INTEGER PRIMARY KEY,
                        moduleName TEXT)''')
        self.cursor.execute('''CREATE TABLE sessions
                       (sessionId INTEGER PRIMARY KEY,
                        module INTEGER,
                        weekday INTEGER,
                        hour INTEGER,
                        minute INTEGER,
                        duration INTEGER,
                        priority INTEGER)''')
        self.cursor.execute('''CREATE TABLE combinations
                       (id INTEGER PRIMARY KEY,
                       combination TEXT,
                       rating INTEGER)''')
        self.database.commit()

    def populateTables(self, configuration):
        i = 0
        for module in configuration:
            # save module
            self.cursor.execute('''INSERT INTO modules (moduleId, moduleName)
                                VALUES(?, ?)''', [i, module['name']])

            moduleWithIds = {'name': module['name'], 'sessions': []}
            # sessions of module
            for session in module['sessions']:
                # save session
                self.cursor.execute('''INSERT INTO sessions (module, weekday,
                                    hour, minute, duration, priority)
                                    VALUES(?, ?, ?, ?, ?, ?)''',
                                    [i, session['weekday'], session['hour'],
                                     session['minute'], session['duration'],
                                     -1])
                sessionDbId = self.cursor.lastrowid
                moduleWithIds['sessions'].append({sessionDbId: session})

            # add module to modules array (in order to get the same id as in the
            # db)
            self.modules.append({i: moduleWithIds})

            i += 1

        self.database.commit()

    def generateAllPossibleCombinations(self):
        # generate list only containing session ids for each module
        sessionIds = []
        for module in self.modules:
            moduleContent = list(module.values())
            thisSessions = []
            thisSessionIds = moduleContent[0]['sessions']
            for sessionId in thisSessionIds:
                thisSessions.append(list(sessionId.keys()))
            sessionIds.append(thisSessions)
        allCombinations = list(itertools.product(*sessionIds))

        # save combinations to database
        self.savePossibleCombinationsToDb(allCombinations)

    def savePossibleCombinationsToDb(self, combinations):
        for combination in combinations:
            combinationJson = json.dumps(combination)
            self.cursor.execute('''INSERT INTO combinations (combination,
                                rating)
                                VALUES(?, ?)''', [combinationJson, 0])
            self.database.commit()
