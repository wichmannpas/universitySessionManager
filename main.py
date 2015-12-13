#!/usr/bin/python3

import configHandler
import priorityHandler


def main():
    userInput = input('[c] Create new config [l] load config: ')
    if userInput[::1] == 'c':
        configHandler.configHandler().createConfig()
    else:
        fileName = input('Enter configuration file name: ')
        configuration = configHandler.configHandler().loadConfig(fileName)
        priorityHandler.priorityHandler(configuration)

if __name__ == '__main__':
    main()
