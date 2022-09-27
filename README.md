# SaveThePicture

[StreetComplete](https://github.com/streetcomplete/StreetComplete) allows an user to embed a photo into an [OpenStreetMap Note](https://wiki.openstreetmap.org/wiki/Notes);
the photo is eventually deleted from the hosting website 7 days after the OpenStreetMap is closed; this prevents any further analysis of the photo; 
this repository takes advantage of GitHub Actions for daily running a [script](src/osmnotes_picturebackup.py) that searches for recently closed OSM Notes and backups
any StreetComplete pictures contained to https://web.archive.org.

## License

Creative Commons Zero v1.0 Universal
