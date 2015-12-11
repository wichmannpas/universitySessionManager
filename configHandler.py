import sys
import json


class configHandler():
    modules = []
    settings = {}

    def __init__(self):
        userInput = input('[c] Create new config [l] load config: ')
        if userInput[::1] == 'c':
            self.createConfig()

    def createConfig(self):
        fileName = input('Enter filename for configuration: ')

        print('Settings')
        print('========')
        self.settings['minDifference'] = int(input('How much time should at '
                                                   'least be between two '
                                                   'sessions? (in minutes) '))

        # add all modules
        while True:
            inputContinue = input('Add another module? [y/n] ')

            if inputContinue[::1] == 'y':
                self.modules.append(self.addModule())
            else:
                break

        # save file
        self.saveConfig(fileName)

    def addModule(self):
        module = {'sessions': []}

        module['name'] = input(' Module name: ')

        print(' Now you can add all available sessions of this module.')
        # add all sessions of this module
        while True:
            inputContin = input('  Add another session to this module? [y/n] ')

            if inputContin[::1] == 'y':
                self.addSession(module)

            else:
                self.printSessions(module)
                break

        return module

    def addSession(self, module):
        # add session
        session = {}

        session['weekday'] = int(input('   Weekday [0-6]: '))
        session['hour'] = int(input('   Start hour: '))
        session['minute'] = int(input('   Start minute: '))
        session['duration'] = int(input('   Length (in minutes): '))
        module['sessions'].append(session)

        # check that time is valid
        if session['hour'] > 23 or session['minute'] > 59:
            print('invalid time.')
            sys.exit(0)

    def printSessions(self, module):
        print(' Overview of sessions in this module')
        print(' ===================================')

        for session in module['sessions']:
            endTime = self.getEndTime(session)

            print('  ' + self.getWeekday(session['weekday']) + ', ' +
                  str(session['hour']) + ':' + str(session['minute']) + '-' +
                  str(endTime['hour']) + ':' + str(endTime['minute']))

        return module

    def getEndTime(self, session):
        hours = session['hour']
        minutes = session['minute'] + session['duration']

        while minutes > 59:
            minutes -= 60
            hours += 1

        if hours > 23:
            print('Invalid session!')
            sys.exit(1)

        return {'hour': hours, 'minute': minutes}

    def getWeekday(self, day):
        if day == 0:
            return 'Monday'
        elif day == 1:
            return 'Tuesday'
        elif day == 2:
            return 'Wednesday'
        elif day == 3:
            return 'Thursday'
        elif day == 4:
            return 'Friday'
        elif day == 5:
            return 'Saturday'
        elif day == 6:
            return 'Sunday'

    def saveConfig(self, fileName):
        fileContent = json.dumps(self.modules)

        config = open(fileName, 'w')
        if config.write(fileContent):
            print('successfully wrote config file.')
        else:
            print('Could not save configuration')
