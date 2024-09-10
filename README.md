# UH Manoa IfA - Image Subtraction for TESS FFI's
This is a simple subtraction pipeline built on top of ISIS, as well as additional utilities from Michael Fausnaugh.

The main script **ingest-sector** should be called on a payload directory of a sector's raw images pulled from MAST. This script will build config, dates, and ref\_list files needed for ISIS. It will then run **quick-smooth**, **isis-make-ref**, **isis-subtract**, **correct-straps**, **bkg-median-filter** on each of the cam/ccd field directories. This will give us our interp, conv, and bkg images. Finally the script will log the sector, field, and image data into a postgres server for use late by our forced potometry service.
