# GoPro trackday event extractor

Status: planning. The specifications are written; no code exists yet.

## Goal

A trackday produces hours of in-car GoPro footage. To evaluate the driving, only the stretches where the track was clear are useful: a curve driven behind another car, during an overtake or after a slide says little about the driver's real pace.

This project reads GoPro footage filmed from inside a race car and writes, for each video, a list of what happened and when: where the track was clear, and where an event took place, such as overtaking, being overtaken, sliding, leaving the track or an obstacle on the road.

It also extracts the GPS track stored inside the GoPro file, so that other software can synchronise the video with a separate GPS logger.

The project is one module of a larger trackday analysis program.

## How it works

```mermaid
flowchart TD
    A[Set of GoPro video files] --> B[1. Check input]
    B --> C[2. Extract GPS]
    C --> G[(name.gpx)]
    B --> D[3. Read signals<br/>picture, sound, motion sensors]
    L[(Event type list<br/>label + description)] --> E
    D --> E[4. Detect events]
    E --> F[5. Build timeline]
    F --> H[6. Write events]
    H --> I[(name-events.txt)]
```

Each video is processed on its own and produces two files with the same base name as the video.

Example of an events file:

```
00:00 warm up
01:44 clear
02:31 offtrack
02:33 clear
```

## Documents

- [Business specification](BUSINESS_SPEC.md): what the module must do.
- [Technical specification](TECHNICAL_SPEC.md): how it is built.

## Example video

The example video will be linked here once it is uploaded.

## Note

This project is not affiliated with or endorsed by GoPro.
