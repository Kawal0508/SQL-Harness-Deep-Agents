#!/bin/sh
# Pin -e so the run does not keep simulating through today.
# Same flags as the README; run from this directory.
java -jar synthea-with-dependencies.jar \
  -p 2000 -s 20260911 -cs 20260911 -r 20260911 -e 20260911 \
  --exporter.baseDirectory ./synthea_output \
  --exporter.csv.export true \
  --exporter.fhir.export false \
  Iowa
