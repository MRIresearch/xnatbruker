# xnatbruker

## Introduction
This application transfers raw Bruker data to an XNAT instance and stores it as an MR Session. DICOM conversion is achieved using `Dicomifier` and NIFTI files are generated using `BrkRaw`. In XNAT the NIFTI files are uploaded into a resource folder called `BIDS` while the Bruker Raw Data is uploaded into a resource folder called `RAWDATA`. 


## Basic usage
The main Python executable is `uploadraw.py` and is called with command-line arguments which are described further below. By default the `[XNATProjectID]` is expected to have already been created on the XNAT instance which minimizes errors.

A minimally viable call to `uploadraw.py` is shown furher below using docker. This would create an MR session called `[XNATSessionID]` for a subject `[XNATSubjectID]` within an existing project `[XNATProjectID]` on an XNAT hosted at `[XNAT host URL]`.

The workflow first copies the rawdata initially situated at `[path/to/raw/bruker/data]` to a unique subfolder within the work directory specified by `--workdir` at `[path/to/work/directory]/[XNATProjectID]/[XNATSubjectID]/[XNATSessionID]/rawdata`. All subsequent processing takes place using this copy of the rawdata to avoid data corruption. 
DICOMs for the raw data will be stored at `[path/to/work/directory]/[XNATProjectID]/[XNATSubjectID]/[XNATSessionID]/dicoms` and a zipped version of this folder will also be stored at `[path/to/work/directory]/[XNATProjectID]/[XNATSubjectID]/[XNATSessionID]/[XNATSubjectID]_[XNATSessionID]_dicoms.zip`; NIFTIs for the raw data will be stored at `[path/to/work/directory]/[XNATProjectID]/[XNATSubjectID]/[XNATSessionID]/niftis`. During processing, users will be asked for their userid and password for gaining access to the specified project in XNAT. These credentials can also be passed to the script to minimize interaction and this is discussed in more detail in the **Advanced Usage** section below.

```
docker run --rm -it -v $PWD:/mnt aacazxnat/xnatbruker:0.3 python  /src/uploadraw.py \
                            [path/to/raw/bruker/data] \
                            --workdir [path/to/work/directory] 
                            --host [XNAT host URL] 
                            --subject [XNATSubjectID] 
                            --session [XNATSessionID] 
                            --project [XNATProjectID]
```

## Advanced Usage
A number of enhancements can be used to automate functionality and extend metadata management.

### Credentials
Userid and passord can be passed automatically either by using the parameters `--user` and `--password` or by using a credentials json file through the `--credentials` parameter. The latter is a more secure way to do this especially if the credentials file is secured using `chmod 0400 credentials.json`

An example of a credentials json file is shown below:
```
{
    "user": "admin",
    "password": "admin"
}
```
In summary then, the workflow will initially use userid and password passed using `--user` and `-password`. If these are missing then the credentials file will be used to obtain the login parameters. If neither of these approaches provides the required credentials then the user will be asked to manually enter them.


### Subject, Session and Project Labels
Rather than pass the Subject, Session and Project Labels directly it is also possible to pass an assignments file using the parameter `--assignment` which associates metadata stored in the raw bruker data with the required labels. The assignments file is a json file with 3 sections, `Labels`, `CustomForms` and `Standard`. The subject, session and project labels are stored in the `Labels` section as shown below:

```
    "Labels":{
    "PROJECT_ID":"BBBUS",
    "SUBJECT_LABEL": "_subject.parameters['SUBJECT_id']",
    "SESSION_LABEL": "_subject.parameters['SUBJECT_study_name']"
    },
```

values prefixed with `_subject.parameters` are fields queried within the Bruker Raw data. If these labels are not defined in the assignment file then the code will also look within the field `_subject.parameters['SUBJECT_remarks']` which is actually the `additional info` field that is available on the bruker console. It will be expecting a string in the form `Project:XNATProjectID   Subject:XNATSubjectID   Session:XNATSessionID` from which the labels can be determined

In summary then, the workflow initially looks for labels defined directly by the parameters `--project`, `--session` and `--subject`. If these are not present then it looks in the `Labels` section of the assignments file for the keys `PROJECT_ID`, `SUBJECT_LABEL` and `SESSION_LABEL`. Finally if these are not present then it attempts to parse the `additional info` text which is stored in `Pvdataset._subject.parameters['SUBJECT_study_comments']` which should be in the format `Project:XNATProjectID   Subject:XNATSubjectID   Session:XNATSessionID`

### Metadata Assignment
In addition to the project, subject and session labels the assignment file can be used to update additional subject and session metadata once the session is created.

#### Custom Forms
Starting in XNAT 1.8.8 custom forms can now be conveniently created in XNAT to handle extensions to the standard XNAT datatypes. in the `CustomForms` section, these fields can be defined by specifying the `FormUUID` as a dictionary element and individual fields within that form can be defined with the source of the data and the datatype. 

In the example below, the `group` variable on the form `14906760-70e0-4056-b9d6-e4f90b30231b` will be updated from the bruker raw data as `_subject.parameters['SUBJECT_referral']` and it will be stored as a string (`text`).

```
    "CustomForms":{
        "14906760-70e0-4056-b9d6-e4f90b30231b": {
        "group": [ "_subject.parameters['SUBJECT_referral']", "text" ],
        "animalType": ["_subject.parameters['SUBJECT_type']", "text"],
        "animalModel": ["_subject.parameters['SUBJECT_remarks']","text"]
        },
        "d8ad043c-cfe6-4cf6-8618-43c256e0f5db": {
        "navigationScore": ["_subject.parameters['SUBJECT_version_nr']", "integer"],
        "completedTrailFollowingTask": ["_subject.parameters['SUBJECT_study_nr']","boolean"]
        },
        "c7736733-7207-45b2-a2db-f05dd6b8792c":{
        "sessionAnasthetic": ["True","boolean"]
        }
    },
```

#### Standard XNAT assignment
Standard XNAT fields can also be set in a similar way using the `Standard` section. 

```
    "Standard":{
        "/data/projects/{PROJECT_ID}/subjects/{SUBJECT_LABEL}":{
           "weight": ["_subject.parameters['SUBJECT_weight']","float"],
           "gender": ["_subject.parameters['SUBJECT_sex_animal']","text"]
        },
        "/data/projects/{PROJECT_ID}/subjects/{SUBJECT_LABEL}/experiments/{SESSION_LABEL}":{
           "coil": ["_subject.parameters['SUBJECT_comment']","text"]
        }
```


## Example
In the `example` folder there is some test data in a zip file which you can extract and test in an XNAT instance.

Here is an example call which assumes that the docker call is made in the top folder of the git repository:
```
cd xnatbruker/example
unzip 20190724_114946_BRKRAW_1_1
cd ..
docker run --rm -it -v $PWD/example:/mnt  aacazxnat/xnatbruker:0.3 python /src/uploadraw.py \
                            /mnt/20190724_114946_BRKRAW_1_1 \
                            --workdir /mnt/work \
                            --host http://192.168.0.31 \
                            --assignment /opt/work/assignments.json \
                            --credentials /opt/work/credentials.json \
```                            

## Version 0.3 Changes
* Credentials and Assignments file added to improve automation and support metadata assignments
* Improved error handling for missing keys in metadata assignments 
* Basic handling of duplicated data - either upoad is skipped or existing data is overwritten. This behavior is managed at a granular level using `--dup_session`, `--dup_nifti`, `--dup_raw` and `dup_metadata` parameters. 

## To do for next Version 0.4
* Provide `--cleanup` flag to clean out the `work` directory.
* Add `Project_ID` to the `dicoms.zip` file to further distinguish it.
* Complete the BIDS conversion workflow.
* Incorporate code to convert DWI bvecs correctly.
