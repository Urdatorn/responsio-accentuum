# Responsio Accentuum 
[![ORCID](media/orcid-badge.svg)](https://orcid.org/0009-0003-3731-4038)
![](media/baseline_prose_py04.gif)

Software to measure accentual responsion and virtual constraints on melody in Greek polystrophic archaic lyric, to begin with and above all the polystrophic 40 polystrophic victory odes of Pindar (comprising 11 379 positions, the random variables of our investigation).[^1] 

For a visualization and explanation of the results, see the companion Github Pages [website](https://urdatorn.github.io/responsio-accentuum/).

This project builds on and generalizes my previous work on the songs of Aristophanes, found [here](https://github.com/Urdatorn/aristophanis-cantica).

## TODO 

- heatmaps with nr of refrains in title 
- make lyric baseline as well (make Frankenstein null baseline strophes by searching odes for lines with the same lengths (or longer, since end is most interesting, and always possible to retrograde heatmapping later) as P4, being careful not to include two lines from the same ode in the same line in diff strophes)
- differences between ol, py, is, ne? compare equistrophic cantica2

[^1]: Four of the preserved odes have no responding parts at all, i.e. no refrains. Note that only 37 of the 40 responding songs have separate strophes and antistrophes, so if the responding unit of interest is the strophe instead of the strophe-antistrophe-epode triad, the corpus is slightly smaller. 

## Copyright and citation

The script `stats_comp.py` contains adaptations of code from the [Greek-Poetry](https://github.com/aconser/Greek-Poetry) repository, which is copyright Anna Conser 2022 under the MIT license. The license is quoted in its entirety in the doc string of that file.

I am also partly using scansions derived from the [Hypotactic website](https://hypotactic.com/latin/index.html), which is under the [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) license. The author David Chamberlain (University of Oregon) interprets the license in the following way:

> All the data on this site is/are licensed as CC-BY 4.0. That means that you can use it as you wish, but if you make significant or extensive use of it in published work you should reference me (David Chamberlain) and this site (hypotactic.com) as the source of the information (this constitutes my interpretation of the licence's "reasonable manner" language). By "data" I mean the tagging of individual syllables of verse with metrical attributes such as quantity, elision, hiatus, synizesis etc., and the identification of those syllables as independent metrical units.* To be clear, I do not intend to place any restrictions that go beyond standard academic attribution conventions; rather, I would like to encourage others to use the data as they will. The licence is intended to reassure you that that's OK.

The present repository itself, however, is under the copyleft GNU GPL 3 license (compatible with the MIT license), which means you are more than welcome to fork and build on this software for your own open-science research, as long as your code retains an equally generous licensing. The author is Albin Ruben Johannes Thörn Cleland, a PhD student at Lund university, Sweden.

![](media/snell-fourth-pythian.png)