#!/usr/bin/env python3
"""
PalmSens MethodSCRIPT example: simple Cyclic Voltammetry (CV) measurement

This example showcases how to run a Cyclic Voltammetry (CV) measurement on
a MethodSCRIPT capable PalmSens instrument, such as the EmStat Pico.

The following features are demonstrated in this example:
  - Connecting to the PalmSens instrument using the serial port.
  - Running a Cyclic Voltammetry (CV) measurement.
  - Receiving and interpreting the measurement data from the device.
  - Plotting the measurement data.

-------------------------------------------------------------------------------
Copyright (c) 2019-2021 PalmSens BV
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

   - Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.
   - Neither the name of PalmSens BV nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.
   - This license does not release you from any requirement to obtain separate 
	  licenses from 3rd party patent holders to use this software.
   - Use of the software either in source or binary form must be connected to, 
	  run on or loaded to an PalmSens BV component.

DISCLAIMER: THIS SOFTWARE IS PROVIDED BY PALMSENS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL THE REGENTS AND CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

# Standard library imports
import datetime
import logging
import os.path
import sys
import csv
import boto3
import PySimpleGUI as sg

# Third-party imports
import matplotlib.pyplot as plt

# Local imports
import palmsens.instrument
import palmsens.mscript
import palmsens.serial


###############################################################################
# Start of configuration
###############################################################################

# COM port of the device (None = auto detect).
DEVICE_PORT = None

# Location of MethodSCRIPT file to use.
MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'

# Location of output files. Directory will be created if it does not exist.
OUTPUT_PATH = 'output'

#dynamoDB tanle name
TABLE_NAME = datetime.datetime.now().strftime('EMStat_Data_%H%M')

# Bucket NameE
BUCKET_NAME = 'eyalschwartz'

###############################################################################
# End of configuration
###############################################################################


def create_dynamoDB_table(table_name, attributes):

    """create dynamoDB table"""
    
    table = boto3.client('dynamodb')
    response = table.create_table(
        AttributeDefinitions=[
            {'AttributeName': attributes[0], 'AttributeType': 'S'},
            {'AttributeName': attributes[1], 'AttributeType': 'S'}
            ],
        TableName=table_name,
        KeySchema=[
        {'AttributeName': attributes[0],'KeyType': 'HASH'},
        {'AttributeName': attributes[1],'KeyType': 'RANGE'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 1,'WriteCapacityUnits': 1},
        TableClass='STANDARD'
        )
  
def dynamoDB_upload(table_name, attributes):
    response = table.put_item(
                TableName= table_name,
                Item={'V': {'S': str(attributes[0])}, 'I': {'S': str(attributes[1])}}
                )
  
def s3_upload(bucket_name, file_path, file_name, folder_name = ''):
    s3 = boto3.resource('s3')
    s3.Bucket(bucket_name).upload_file(file_path, folder_name + file_name)
    

LOG = logging.getLogger(__name__)

def write_curves_to_csv(file, curves):
    """Write the curves to file in CSV format.

    `file` must be a file-like object in text mode with newlines translation
    disabled.

    The header row is based on the first row of the first curve. It is assumed
    that all rows in all curves have the same data types.
    """
    # NOTE: Although the extension is CSV, which stands for Comma Separated
    # Values, a semicolon (';') is used as delimiter. This is done to be
    # compatible with MS Excel, which may use a comma (',') as decimal
    # separator in some regions, depending on regional settings on the
    # computer. If you use anoter program to read the CSV files, you may need
    # to change this. The CSV writer can be configured differently to support
    # a different format. See
    # https://docs.python.org/3/library/csv.html#csv.writer for all options.
    # NOTE: The following line writes a Microsoft Excel specific header line to
    # the CSV file, to tell it we use a semicolon as delimiter. If you don't
    # use Excel to read the CSV file, you might want to remove this line.
    file.write('sep=;\n')
    writer = csv.writer(file, delimiter=';')
    for curve in curves:
        # Write header row.
        writer.writerow(['%s [%s]' % (value.type.name, value.type.unit) for value in curve[0]])
        # Write data rows.
        for package in curve:
            writer.writerow([value.value for value in package])


def main():
    """Run the example."""
    #GUI parameters
    file_list_column = [
    [sg.Push(),sg.Button("Clean"), sg.Push()],
    [sg.Push(),sg.Button("Platinum_Black"), sg.Push()],
    [sg.Push(),sg.Button("rGO"), sg.Push()],
    [sg.Push(),sg.Button("Chitosan-CNT"), sg.Push()],
    [sg.Push(),sg.Button("MoS2_a"), sg.Push()],
    [sg.Push(),sg.Button("MoS2_b"), sg.Push()],
    [sg.Push(),sg.Button("MS2_b"), sg.Push()]
    ]

    image_viewer_column = [
    [sg.Text(size=(40,1), key='-OUTPUT-')],
    [sg.VPush()],
    [sg.Push(),sg.Text("Plot will appear here:"),sg.Push()],
    [sg.Text(size=(40, 1), key="-TOUT-")],
    [sg.Push(),sg.Image(key="-IMAGE-"),sg.Push()],
    [sg.Button("Start"),sg.Push(), sg.Button("Exit")],
    ]

    # ----- Full layout -----
    layout = [
    [sg.Column(file_list_column),
        sg.VSeperator(),
        sg.Column(image_viewer_column)]
    ]
    
    window = sg.Window("OncoRedox Coating", icon='./OncoRedox-logo.ico').Layout(layout)
    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            break
        
        if event== "Clean":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "Clean"
        elif event == "Platinum_Black":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "Platinum_Black"
        elif event == "rGO":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "rGO"
        elif event == "Chitosan-CNT":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "Chitosan-CNT"
        elif event == "MoS2_a":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "MoS2 a"
        elif event == "MoS2_b":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "MoS2 b"
        elif event == "MS2_b":
            MSCRIPT_FILE_PATH = 'scripts/example_cv.mscr'
            TEST = "MS2 b"
        
        window['-OUTPUT-'].update('Running ' + TEST + " procedure. Press \"Start\" to execute...")

        if event== "Start":
            # Configure the logging.
            logging.basicConfig(level=logging.DEBUG, format='[%(module)s] %(message)s',
                                stream=sys.stdout)
            # Uncomment the following line to reduce the log level for our library.
            # logging.getLogger('palmsens').setLevel(logging.INFO)
            # Disable excessive logging from matplotlib.
            logging.getLogger('matplotlib').setLevel(logging.INFO)

            port = DEVICE_PORT
            if port is None:
                port = palmsens.serial.auto_detect_port()

            # Create and open serial connection to the device.
            with palmsens.serial.Serial(port, 1) as comm:
                device = palmsens.instrument.Instrument(comm)
                device_type = device.get_device_type()
                LOG.info('Connected to %s.', device_type)

                # Read and send the MethodSCRIPT file.
                LOG.info('Sending MethodSCRIPT.')
                device.send_script(MSCRIPT_FILE_PATH)

                # Read the result lines.
                LOG.info('Waiting for results.')
                result_lines = device.readlines_until_end()

            # Store results in file.
            os.makedirs(OUTPUT_PATH, exist_ok=True)
            result_file_name = datetime.datetime.now().strftime('Test_Run-%H%M') #
            result_file_path = os.path.join(OUTPUT_PATH, result_file_name)


            # Parse the result.
            curves = palmsens.mscript.parse_result_lines(result_lines)
            
            # Write to csv
            with open(result_file_path + '.csv', 'wt', newline='', encoding='ascii') as file:
                write_curves_to_csv(file, curves)
                
            #    for curve in curves:
            #        for package in curve:
            #            X = [str(value) for value in package]
            #            dynamoDB_upload(TABLE_NAME, X)
                    
            # Log the results.
            for curve in curves:
                for package in curve:
                        X = [str(value) for value in package]
                        LOG.info(X) 
                                    
            # Get the applied potentials (first column of each row)
            applied_potential = palmsens.mscript.get_values_by_column(curves, 0)
            # Get the measured currents (second column of each row)
            measured_current = palmsens.mscript.get_values_by_column(curves, 1)

            # Plot the results.
            plt.figure(1)
            plt.plot(applied_potential, measured_current)
            plt.title('Voltammogram')
            plt.xlabel('Applied Potential (V)')
            plt.ylabel('Measured Current (A)')
            plt.grid(b=True, which='major')
            plt.grid(b=True, which='minor', color='b', linestyle='-', alpha=0.2)
            plt.minorticks_on()
            plt.savefig(result_file_path + '.png')
            
            
            #upload files to S3
           # s3_upload(BUCKET_NAME, result_file_path + '.csv', result_file_name + '.csv', result_file_name + '/')
           # s3_upload(BUCKET_NAME, result_file_path + '.png', result_file_name + '.png', result_file_name + '/')

            plt.show()
    window.close()

if __name__ == '__main__':
    main()
