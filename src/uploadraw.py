import os
import getpass
import xnat
import requests
import brkraw as br
import subprocess
import shutil

__version__=0.1


def isTrue(arg):
    return arg is not None and (arg == 'Y' or arg == '1' or arg == 'True')

def get_parser():
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter
    parser = ArgumentParser(description="upload resource sto XNAT")
    parser.add_argument("brukerdir", default="./data", help="root directory of bruker raw data")
    parser.add_argument("--workdir", default="./work", help="work directory")
    parser.add_argument("--host", default="https://cnda.wustl.edu", help="CNDA host", required=True)
    parser.add_argument("--session", help="Session ID or session label for uploadDicomZip ", required=True)
    parser.add_argument("--subject", help="subject ID or subject label for uploadDicomZip", required=True)
    parser.add_argument("--project", help="Project", required=True)
    parser.add_argument("--user", help="user", required=False)
    parser.add_argument("--password", help="password", required=False)    
    parser.add_argument('--version', action='version', version='%(prog)s 1')
    parser.add_argument('--projcreate', action='store',
        help='Can create a project if it doesnt exist. Default is false', default="N")
    return parser



def upload_to_xnat(brukerdir,workdir,host,session,subject,project,user,password,projcreate,addArgs=None):
    
    rawdataset = br.load(brukerdir)
    print("upload to xnat started.")
    print("Summary of session upload:")
    rawdataset.info()

    # copy rawdata to work folder
    rootrawdatadir=os.path.join(workdir,project,subject,session,'rawdata')
    if not os.path.exists(rootrawdatadir):
        os.makedirs(rootrawdatadir)
    rawdatadir=os.path.join(rootrawdatadir,os.path.basename(brukerdir))
    print("Copying raw bruker data from {} to {}".format(brukerdir,rawdatadir))
    if not os.path.exists(rawdatadir):
        shutil.copytree(brukerdir,rawdatadir)

    with xnat.connect(server=host,user=user,password=password) as connection:
        try:
            project_inst = connection.projects[project]
        except Exception as e:
            project_inst = None
            if not projcreate:
                print("Project {} doesn't exist and --projcreate parameter is set to 'N' so exitting".format(project))
                return
            else:
                project_inst = connection.classes.ProjectData(parent=connection, name=project,id=project,description=project)

        try:
            subject_inst = connection.projects[project].subjects[subject]
        except Exception as e:
            print("Subject {} doesn't exist. Creating".format(subject))
            subject_inst = connection.classes.SubjectData(parent=project_inst, label=subject)


        # populate using custom fields - note that you will need to restart tomcat
        # after defining custom fields to avoid issues. Also uppercase letters used in XNAT
        # to define variables are accessed as all lower case. e.g. Animal_Model accessed as 
        # animal_model
        subject_inst.fields['animal_type']=rawdataset._subject.parameters['SUBJECT_type']
        subject_inst.fields['animal_model']=rawdataset._subject.parameters['SUBJECT_remarks']
        # populate using standard demographics
        subject_inst.demographics.gender = 'female'


        # create MR session
        try:
            mrsession_inst = connection.projects[project].subjects[subject].experiments[session]
            print("MR Session {} already exists. This upload will be cancelled.".format(session))
            SESSION_EXISTS=True
        except Exception as e:
            print("MR Session {} doesn't exist. This will be created".format(session))
            SESSION_EXISTS=False
            
        if not SESSION_EXISTS:
            dicomdir=os.path.join(workdir,project,subject,session,'dicoms')
            if not os.path.exists(dicomdir):
                os.makedirs(dicomdir)
            to_dicom_command="dicomifier to-dicom {} {}".format(rawdatadir, dicomdir).split()
            print(subprocess.check_output(to_dicom_command))
            print("Dicoms for MR Session {} generated using dicomifier".format(session))

            zipfile = os.path.join(workdir,project,subject,session,'{}_{}_dicoms'.format(subject,session))
            shutil.make_archive(zipfile , 'zip', dicomdir)
            print("Dicoms Archived for MR Session {} and ready for upload".format(session))

            new_session = connection.services.import_(zipfile + '.zip', project=project,subject=subject)
            new_session.label = session
            session_inst = connection.projects[project].experiments[session]
            print("MR Session {} created on XNAT and Dicoms uploaded".format(session))

            # create and upload niftis
            currdir=os.getcwd()
            niftidir=os.path.join(workdir,project,subject,session,'niftis')
            if not os.path.exists(niftidir):
                os.makedirs(niftidir)
            os.chdir(niftidir)
            to_niiall_command="brkraw tonii_all -b {}".format(rootrawdatadir).split()
            print(subprocess.check_output(to_niiall_command))
            os.chdir(currdir)
            bids_resource = connection.classes.ResourceCatalog(parent=session_inst,label="BIDS")
            bids_resource.upload_dir(directory = niftidir,overwrite = True, method = 'tgz_file')
            print("BIDS conversion for MR Session {} generated using brkraw toni_all and uploaded to XNAT".format(session))
          
            # upload raw data as tgz file
            rawdata_resource = connection.classes.ResourceCatalog(parent=session_inst,label="RAWDATA")
            rawdata_resource.upload_dir(directory = rawdatadir,overwrite = True, method = 'tgz_file')
            print("Bruker Raw Data  for MR Session {} uploaded to XNAT".format(session))
 

def main():
    args, unknown_args = get_parser().parse_known_args()
    host = args.host
    
    brukerdir = os.path.abspath(args.brukerdir)
    workdir = os.path.abspath(args.workdir)
    host = args.host

    if args.user is None:
        user = input("User: ")
    else:
        user = args.user

    if args.password is None:
        password = getpass.getpass()
    else:
        password = args.password

    
    session = args.session
    subject = args.subject
    project = args.project
    projcreate= isTrue(args.projcreate)

    additionalArgs = unknown_args if unknown_args is not None else []

    upload_to_xnat(brukerdir,workdir,host,session,subject,project,user,password,projcreate,additionalArgs)

   
# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()