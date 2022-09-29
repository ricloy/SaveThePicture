# SaveThePicture

[StreetComplete](https://github.com/streetcomplete/StreetComplete) allows its users to embed photos into [OpenStreetMap Notes](https://wiki.openstreetmap.org/wiki/Notes);
each photo is eventually deleted from the hosting website 7 days after the corresponding note is closed, thus preventing any further analysis of the photo thereafter; 
this repository takes advantage of GitHub Actions for daily running a [script](src/osmnotes_picturebackup.py) that searches for recently closed OSM Notes created in Italy and backups
any StreetComplete pictures contained to https://web.archive.org.

## License

Creative Commons Zero v1.0 Universal
