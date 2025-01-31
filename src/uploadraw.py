import os
import getpass
import xnat
import requests
import brkraw as br
import subprocess
import shutil
import json
import re

__version__=0.4

def getParams(pardict, key):
    if key is not None and pardict is not None:
        if key in pardict:
            return pardict[key] 
    return None


def loadParams(pardict, key, value):
    if key is not None and pardict is not None:
        if not key in pardict:
            pardict[key]=value   

def isTrue(arg):
    return arg is not None and (arg == 'Y' or arg == '1' or arg == 'True' or arg == 'true')

def get_parser():
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter
    parser = ArgumentParser(description="upload resource sto XNAT")
    parser.add_argument("brukerdir", default="./data", help="root directory of bruker raw data")
    parser.add_argument("--workdir", default="./work", help="work directory")
    parser.add_argument("--assignment", help="assignment file")
    parser.add_argument("--credentials", help="credential file")
    parser.add_argument("--host", default="https://cnda.wustl.edu", help="CNDA host", required=True)
    parser.add_argument("--session", help="Session label", required=False)
    parser.add_argument("--subject", help="Subject label", required=False)
    parser.add_argument("--project", help="Project", required=False)
    parser.add_argument("--user", help="user", required=False)
    parser.add_argument("--password", help="password", required=False)    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--dup_session', action='store',
        help='handle session duplicates. skip, overwrite or append', default="append")
    parser.add_argument('--dup_nifti', action='store',
        help='handle nifti session duplicates. skip or overwrite', default="skip")
    parser.add_argument('--dup_raw', action='store',
        help='handle raw duplicates. skip or overwrite', default="skip")
    parser.add_argument('--dup_metadata', action='store',
        help='handle metadata updates for session duplicates. skip or overwrite', default="overwrite")
    parser.add_argument('--projcreate', action='store',
        help='Can create a project if it doesnt exist. Default is false', default="N")
    return parser

def initialize_labels():
    assign_labels={}
    return assign_labels

def overwrite_labels(project, subject, session):
    assign_labels={}
    if project is not None:
        loadParams(assign_labels,"PROJECT_ID",project)
    if subject is not None:
        loadParams(assign_labels,"SUBJECT_LABEL",subject)
    if session is not None:
        loadParams(assign_labels,"SESSION_LABEL",session)

    return assign_labels


def process_labels(brkdata, assign_dict,assign_labels):
    
    # Process Labels
    try:
        LABELS=assign_dict["Labels"]
    except KeyError:
        print("Labels not defined in assignment dict {}".format(str(assign_dict)))
        return assign_labels

    for itemkey,itemvalue in LABELS.items():
        if ('_subject.parameters' in itemvalue):
            try:
                brkkey = itemvalue.split("['")[1].split("']")[0]
                brkvalue = brkdata._subject.parameters[brkkey]
                loadParams(assign_labels,itemkey,str(brkvalue))
            except Exception:
                print("Brkdata references not entered properly in {}. Missing matching '[ ]'".format(str(assign_dict)))
        else:
            loadParams(assign_labels,itemkey,str(itemvalue))

    return assign_labels


def process_routing(brkdata, assign_labels):
    ROUTING=''
    # Check for subject remarks which may contain routing information
    try:
        ROUTING=brkdata._subject.parameters['SUBJECT_study_comment']
    except Exception:
        print("problem getting routing information from SUBJECT_remarks")
        return assign_labels

    if "Project:" in ROUTING:
        PROJECT_ID=ROUTING.split("Project:")[1].strip().split(' ')[0]
        loadParams(assign_labels,"PROJECT_ID",PROJECT_ID)
    if "Subject:" in ROUTING:
        SUBJECT_LABEL=ROUTING.split("Subject:")[1].strip().split(' ')[0]
        loadParams(assign_labels,"SUBJECT_LABEL",SUBJECT_LABEL)
    if "Session:" in ROUTING:
        SESSION_LABEL=ROUTING.split("Session:")[1].strip().split(' ')[0]
        loadParams(assign_labels,"SESSION_LABEL",SESSION_LABEL)

    return assign_labels

def substitute_labels(querystring, querylabels,assign_labels):
    for label in querylabels:
        labelkey=label.replace('{','').replace('}','')
        try:
            labelvalue = assign_labels[labelkey]
            querystring = querystring.replace(label,labelvalue)
        except Exception:
            print("problem obtaining label {}".format(label))
            return None

    return querystring


def process_xnat_standard(connection, assign_dict, brkdata, assign_labels,SESSION_EXISTS,dupaction):
    if SESSION_EXISTS and dupaction == 'skip':
        print("Session already exists. Will not be updating metadata as dupaction set to {}.".format(dupaction))
        return 

    # Process Labels
    try:
        STANDARD=assign_dict["Standard"]
    except KeyError:
        print("Standard not defined in assignment dict {}".format(str(assign_dict)))
        return

    for itemkey,itemvalue in STANDARD.items():
        for varkey,varvalue in itemvalue.items():
            if len(varvalue) > 0:
                if ('_subject.parameters' in varvalue[0]):
                    try:
                        brkkey = varvalue[0].split("['")[1].split("']")[0]
                        brkvalue = brkdata._subject.parameters[brkkey]
                        if len(varvalue) > 1:
                            if varvalue[1] == 'text':
                                brkvalue=str(brkvalue)
                            elif varvalue[1] == 'float':
                                brkvalue=float(str(brkvalue))
                            elif varvalue[1] == 'integer':
                                brkvalue=int(str(brkvalue))
                            elif varvalue[1] == 'boolean':
                                brkvalue=isTrue(str(brkvalue))
                            else:
                                brkvalue=str(brkvalue)
                        else:
                            brkvalue=str(brkvalue)
                    
                    except Exception:
                        print("Brkdata reference {} is missing or format of entry is wrong in assignment file".format(brkkey))
                        continue
                else:
                    brkvalue = varvalue[0]
                    if len(varvalue) > 1:
                        if varvalue[1] == 'text':
                            brkvalue=str(brkvalue)
                        elif varvalue[1] == 'float':
                            brkvalue=float(str(brkvalue))
                        elif varvalue[1] == 'integer':
                            brkvalue=int(str(brkvalue))
                        elif varvalue[1] == 'boolean':
                            brkvalue=isTrue(str(brkvalue))
                        else:
                            brkvalue=str(brkvalue)
                    else:
                        brkvalue=str(brkvalue)

                # find variables in itemkey
                query_labels = re.findall(r'\{.*?\}',itemkey)
                apistring=substitute_labels(itemkey,query_labels,assign_labels)
                if SESSION_EXISTS and dupaction == "overwrite" and apistring is not None:
                    resp=connection.get(apistring,query={"format": "json"})
                    respjson=resp.json()
                    overwriteval=getParams(respjson['items'][0]['children'][0]['items'][0]['data_fields'],varkey)
                    if overwriteval is None:
                        overwriteval = getParams(resp.json()['items'][0]['data_fields'],varkey)
                    if overwriteval is not None:
                        print("Session already exists; the action {} will override values. in the database\nThe variable = {}:\nold value: {}\n will be overwritten with:\nnew value: {}\n".format(apistring + "/" + varkey,varkey,str(overwriteval),str(brkvalue)))

                if apistring is not None:
                    resp=connection.put(apistring,query={varkey: brkvalue})


def process_xnat_custom(connection, assign_dict, brkdata, assign_labels, project, subject, session,SESSION_EXISTS,dupaction):

    if SESSION_EXISTS and dupaction == 'skip':
        print("Session already exists. Will not be updating metadata as dupaction set to {}.".format(dupaction))
        return 

    # Process Labels
    try:
        CUSTOM=assign_dict["CustomForms"]
    except KeyError:
        print("Custom not defined in assignment dict {}".format(str(assign_dict)))
        return

    for itemkey,itemvalue in CUSTOM.items():
        customdict={}
        customdict[itemkey]={}
        for varkey,varvalue in itemvalue.items():
            if len(varvalue) > 0:
                if ('_subject.parameters' in varvalue[0]):
                    try:
                        brkkey = varvalue[0].split("['")[1].split("']")[0]
                        brkvalue = brkdata._subject.parameters[brkkey]
                        if len(varvalue) > 1:
                            if varvalue[1] == 'text':
                                brkvalue=str(brkvalue)
                            elif varvalue[1] == 'float':
                                brkvalue=float(str(brkvalue))
                            elif varvalue[1] == 'integer':
                                brkvalue=int(str(brkvalue))
                            elif varvalue[1] == 'boolean':
                                brkvalue=isTrue(str(brkvalue))
                            else:
                                brkvalue=str(brkvalue)
                        else:
                            brkvalue=str(brkvalue)
                    
                    except Exception:
                        print("Brkdata reference {} is missing or format of entry is wrong in assignment file".format(brkkey))
                        continue
                else:
                    brkvalue = varvalue[0]
                    if len(varvalue) > 1:
                        if varvalue[1] == 'text':
                            brkvalue=str(brkvalue)
                        elif varvalue[1] == 'float':
                            brkvalue=float(str(brkvalue))
                        elif varvalue[1] == 'integer':
                            brkvalue=int(str(brkvalue))
                        elif varvalue[1] == 'boolean':
                            brkvalue=isTrue(str(brkvalue))
                        else:
                            brkvalue=str(brkvalue)
                    else:
                        brkvalue=str(brkvalue)

                customdict[itemkey][varkey]=brkvalue

        # find Custom form and variables for project
        apistring=None
        cfieldjson=None
        resp=connection.get('/xapi/customforms',query={'projectId': project})
        cform_json=resp.json()
        for cform in cform_json:
            # Is this one of our custom forms?
            if cform["formUUID"] == itemkey:
                if "subjectData" in cform["path"]:
                    resp=connection.get('/xapi/custom-fields/projects/{}/subjects/{}/fields'.format(project,subject))
                    cfieldjson=resp.json()
                    apistring='/xapi/custom-fields/projects/{}/subjects/{}/fields'.format(project,subject)

                elif "SessionData" in cform["path"]:
                    resp=connection.get('/xapi/custom-fields/projects/{}/subjects/{}/experiments/{}/fields'.format(project,subject, session))
                    cfieldjson=resp.json()
                    apistring='/xapi/custom-fields/projects/{}/subjects/{}/experiments/{}/fields'.format(project,subject,session)
                else:
                    print("XNAT Custom type {} not recognized. Custom form update skipped".format())
                    return
                if itemkey in cfieldjson.keys():
                    for cfield_key, cfield_values in cfieldjson[itemkey].items():
                        if cfield_key not in customdict[itemkey].keys():
                            customdict[itemkey][cfield_key]=cfield_values
        if apistring is not None:
            if SESSION_EXISTS and dupaction == "overwrite" and itemkey in cfieldjson.keys():
                print("Session already exists. variables for form {}:\n{}\n will be overwritten with:\n{}\n.".format(itemkey, str(cfieldjson[itemkey]),str(customdict)))
            resp=connection.put(apistring,json=customdict)
        else:
            print("form {} not available for this project {}. Metadata update not supported.".format(itemkey,project))


def dicomify(rawdatadir, dicomdir, zipfile, session):
    to_dicom_command="dicomifier to-dicom {} {}".format(rawdatadir, dicomdir).split()
    print(subprocess.check_output(to_dicom_command))
    print("Dicoms for MR Session {} generated using dicomifier".format(session))
    
    shutil.make_archive(zipfile , 'zip', dicomdir)
    print("Dicoms Archived for MR Session {} and ready for upload".format(session))

def create_session(connection, zipfile,project, subject,session, mrsession_inst):

    new_session = connection.services.import_(zipfile + '.zip', quarantine=False, overwrite='delete', project=project,subject=subject,experiment=session, import_handler="DICOM-zip")
    session_inst = connection.projects[project].experiments[session]
    print(f"MR Session {session_inst} for label {session} created on XNAT and Dicoms uploaded")
    return session_inst

def upload_nifti(connection, niftidir,currdir,rootrawdatadir, session_inst, NIFTI_EXISTS, dupaction):

    if NIFTI_EXISTS and dupaction == 'skip':
        print("Nifti data already already exists in session. Will not be recreating.")
        bids_resource = session_inst.resources['BIDS']
        return bids_resource

    if NIFTI_EXISTS and dupaction == 'overwrite':
        connection.delete("/data/experiments/{}/resources/{}".format(session_inst.id,'BIDS'))
        print ("Deleting the existing resource {} for session {}".format('BIDS',session_inst.label))

    os.chdir(niftidir)
    to_niiall_command="brkraw tonii_all -b {}".format(rootrawdatadir).split()
    print(subprocess.check_output(to_niiall_command))
    os.chdir(currdir)
    bids_resource = connection.classes.ResourceCatalog(parent=session_inst,label="BIDS")
    bids_resource.upload_dir(directory = niftidir,overwrite = True, method = 'tgz_file')
    print("BIDS conversion for MR Session {} generated using brkraw toni_all and uploaded to XNAT".format(session_inst.label))

    return bids_resource

def upload_raw(connection, niftidir,currdir,rawdatadir, session_inst, RAW_EXISTS, dupaction):

    if RAW_EXISTS and dupaction == 'skip':
        print("RAW data already already exists in session. Will not be recreating.")
        rawdata_resource = session_inst.resources['RAWDATA']
        return rawdata_resource

    if RAW_EXISTS and dupaction == 'overwrite':
        connection.delete("/data/experiments/{}/resources/{}".format(session_inst.id,'RAWDATA'))
        print ("Deleting the existing resource {} for session {}".format('RAWDATA',session_inst.label))

    rawdata_resource = connection.classes.ResourceCatalog(parent=session_inst,label="RAWDATA")
    rawdata_resource.upload_dir(directory = rawdatadir,overwrite = True, method = 'tgz_file')
    print("Bruker Raw Data  for MR Session {} uploaded to XNAT".format(session_inst.label))

    return rawdata_resource


def upload_to_xnat(brukerdir,workdir,host,session_arg,subject_arg,project_arg,user,password,projcreate,assign_dict, dup_session,dup_nifti,dup_raw, dup_metadata, addArgs=None):
    
    rawdataset = br.load(brukerdir)
    print("upload to xnat started.")
    print("Summary of session upload:")
    rawdataset.info()
    
    assign_labels =initialize_labels()
    if assign_dict is not None:
        assign_labels=process_labels(rawdataset,assign_dict,assign_labels)
    assign_labels=process_routing(rawdataset,assign_labels)
    assign_labels =overwrite_labels(project_arg,subject_arg,session_arg)

    project = None
    subject = None
    session = None
    try:
        project=assign_labels["PROJECT_ID"]
        subject=assign_labels["SUBJECT_LABEL"]
        session=assign_labels["SESSION_LABEL"]
    except Exception as e:
        print("Problems obtaining project, subject or session")


    if project is not None and subject is not None and session is not None:
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
       
            # create MR session
            SESSION_SKIP=False
            try:
                mrsession_inst = connection.projects[project].subjects[subject].experiments[session]


                if dup_session == 'skip':
                    print(f"MR Session {mrsession_inst} for label {session} already exists and duplicate action is set to skip. Session will not be created - Dicoms will not be uploded. You can change default duplicate action for sessions using --dup_session")
                    SESSION_SKIP = True
                elif dup_session =='overwrite':
                    print(f"MR Session {mrsession_inst} for label {session} already exists and duplicate action is set to delete. You can change default duplicate action for sessions using --dup_session")
                    connection.delete("/data/projects/{}/subjects/{}/experiments/{}".format(project,subject,session))
                    print ("Deleting the existing session {}".format(session))
                    print("MR Session {} doesn't exist. This will be created".format(session))
                    mrsession_inst = connection.classes.MrSessionData(parent=subject_inst, label=session)
                else:
                    import pytz
                    datetime_utc = pytz.timezone("UTC").localize(datetime.datetime.now())
                    datetime_mtc = datetime_utc.astimezone(pytz.timezone("MST"))
                    datestamp = datetime_mtc.strftime("%Y-%m-%d-%H-%M-%S")
                    new_session_label = session + "_" + datestamp
                    print(f"MR Session {mrsession_inst} for label {session} already exists. Session will be uploaded to a new session_label {new_session_label}.")
                    mrsession_inst = connection.classes.MrSessionData(parent=subject_inst, label=new_session_label)
                    session = new_session_label
                
            except Exception as e:
                print("MR Session {} doesn't exist. This will be created".format(session))
                mrsession_inst = connection.classes.MrSessionData(parent=subject_inst, label=session)
                
            dicomdir=os.path.join(workdir,project,subject,session,'dicoms')
            if not os.path.exists(dicomdir):
                os.makedirs(dicomdir)
            zipfile = os.path.join(workdir,project,subject,session,'{}_{}_dicoms'.format(subject,session))
            dicomify(rawdatadir, dicomdir, zipfile, session)

            # Create Session
            if not SESSION_SKIP:
                session_inst=create_session(connection, zipfile,project, subject,session, mrsession_inst)
            else:
                session_inst = mrsession_inst

            # create and upload niftis
            try:
                bids_resource = session_inst.resources['BIDS']
                NIFTI_EXISTS=True
            except Exception as e:
                print("MR NIFTI Resource {} doesn't exist for session {}. This will be created".format('BIDS',session))
                NIFTI_EXISTS=False

            currdir=os.getcwd()
            niftidir=os.path.join(workdir,project,subject,session,'niftis')
            if not os.path.exists(niftidir):
                os.makedirs(niftidir)
            bids_resource = upload_nifti(connection, niftidir,currdir,rootrawdatadir,session_inst, NIFTI_EXISTS,dup_nifti)
            
            # upload raw data as tgz file
            try:
                rawdata_resource = session_inst.resources['RAWDATA']
                RAW_EXISTS=True
            except Exception as e:
                print("MR RAWDATA Resource {} doesn't exist for session {}. This will be created".format('RAWDATA',session))
                RAW_EXISTS=False

            rawdata_resource = upload_raw(connection, niftidir,currdir,rawdatadir,session_inst, RAW_EXISTS,dup_nifti)

            # update Subject and Session
            if assign_dict is not None:
                process_xnat_standard(connection,assign_dict,rawdataset,assign_labels,SESSION_EXISTS,dup_metadata)
                process_xnat_custom(connection,assign_dict,rawdataset,assign_labels,project, subject, session,SESSION_EXISTS,dup_metadata)


def main():
    args, unknown_args = get_parser().parse_known_args()
    host = args.host
    
    brukerdir = os.path.abspath(args.brukerdir)
    if args.workdir is None:
        workdir="/opt/work"
    else:
        workdir = os.path.abspath(args.workdir)

    assign_dict=None
    if args.assignment is not None:
        assignment = os.path.abspath(args.assignment)
        if os.path.exists(assignment):
            with open(assignment, 'r') as infile:
                assign_dict = json.load(infile)

    cred_dict = None
    cred_user = None 
    cred_pwd = None


    if args.credentials is not None:
        credentials = os.path.abspath(args.credentials)
        if os.path.exists(credentials):
            with open(credentials, 'r') as infile:
                cred_dict = json.load(infile)
                cred_user = getParams(cred_dict,"user")
                cred_pwd = getParams(cred_dict,"password")

    if args.user is not None:
        user = args.user
    elif cred_user is not None:
        user = cred_user       
    else:
        user = input("User: ")

    if args.password is not None:
        password = args.password
    elif cred_pwd is not None:
        password = cred_pwd
    else:
        password = getpass.getpass()
   
    session = args.session
    subject = args.subject
    project = args.project
    projcreate= isTrue(args.projcreate)
    dup_session = args.dup_session
    dup_nifti = args.dup_nifti
    dup_raw = args.dup_raw
    dup_metadata = args.dup_metadata

    additionalArgs = unknown_args if unknown_args is not None else []

    print(f"Running {__file__} v{__version__}")

    upload_to_xnat(brukerdir,workdir,host,session,subject,project,user,password,projcreate,assign_dict,dup_session,dup_nifti,dup_raw, dup_metadata, additionalArgs)

   
# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
