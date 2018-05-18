'''
Independent module or rather script to check consistency of data.

Checks to perform:
- uniqueness of locations in static data.
- no duplication of sources within a device.
- location <-> zone ia a one-to-one relationship.
- feeds require a zone_id if the device-id is MusicCast
'''

import sys
import json


def main():
    # import json file
    try: filename = sys.argv[1]
    except IndexError:
        print 'I need a filename as first argument.'
        return
    with open(filename, 'r') as fh:
        data = json.load(fh)
    print data
    return

if __name__ == '__main__':
    main()