# xnatbruker
Script to transfer raw Bruker data to an XNAT instance. Python executable is `uploadraw.py` with the following arguments. By default the `XNATProjectID` is expected to have already been created on the XNAT instance - this prevents the erroneous creation of mistyped projects.

```
docker run --rm -it -v $PWD:/mnt aacazxnat/xnatbruker:0.2 python  /src/uploadraw.py \
                            [path/to/raw/bruker/data] \
                            --workdir [path/to/work/directory] 
                            --host [XNAT host URL] 
                            --subject [XNATSubjectID] 
                            --session [XNATSessionID] 
                            --project [XNATProjectID]

```

Here is an example call:
```

docker run --rm -it -v $PWD:/mnt aacazxnat/xnatbruker:0.2 python /src/uploadraw.py \
                            /mnt/sampledata/20190724_114946_BRKRAW_1_1 \
                            --workdir /mnt/work 
                            --host http://192.168.0.31 
                            --subject rat010 
                            --session rat010_MR_session001 
                            --project BBBUS
```

In the `example` folder there is some test data in a zip file which you can extract and test in an XNAT instance.