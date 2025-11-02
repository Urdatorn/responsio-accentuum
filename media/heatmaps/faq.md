# How to interpret the heatmaps

The heatmap shows all syllables of the ode, with each syllable colored according to how high it scores at a metric called "melodic compatibility", which can be at the most 1, and at the least 1/2 (or slighly more[^1]).

Put simply, a compatibility score of 1 means that if Pindar had wanted to compose a melody that satisfied both the following conditions, he could have: 

1. perfectly matched the natural melody of the pitch accents of the language and
2. moved up or down (i.e. didn't repeat the pitch of the note setting the previous syllable).

The lower the score, the less the melody (i.e. any melody!) would have accomodated the pitch accents. Specifically, the score gives the portion of strophes in which the melody rose as the pitch accent fell, or vice versa, so that a score of, say, 8/13 means that no matter whether Pindar decided to let the melody rise or fall while singing this syllable, his melody would contradict the prosody of at least five strophes. 

Importantly, it is perfectly possible to know the above hypothetical or conditional fact about melodic constraints regardless of whether Pindar *actually* did or even would have wanted to compose such a melody, something we will never know, barring the unlikely discovery of a Pindaric musical papyrus or inscription.

# An example

As long as one bears in mind that there can be neither pretention of restoring Pindar's original music nor of achieving any aesthetic pleasure or artistic merit, it is possible to construct simple example melodies of the maximum vivacity (number of non-repeating pitch classes) achievable while respecting the prosody of all strophes. 

For the sake of the following example, which consists of the first two lines of the famous first Olympian ode, we really only need to evoke one rule: that the melody rises in preparation of a syllable with an acute accent (see fourth interval, first line, and both fourth, ninth and twelfth, second line). We also let the melody rest whenever the accents of the different strophes disagree, in other words, wherever the heatmap is less than perfectly bright yellow. (This is the trivial way out of incompatibility, but it is conceivable if not certain that the willingness to accept contradictions came in degrees, and that the two other options (either overriding the *prosody* or perverting the *melody* of at most half of the strophes, both distinguished by not treating all strophes equally) united with it to provide a flexible palette of meta-musical strategies for scoring refrains.)

Lastly, we let the piece begin a reckless and accent-defying large upwards leap, a conventional *incipit* we see in several Hellenistic pieces, like the epitaph of Seikilos. (Note also that the fact that the first syllable has full score is useless since there is no intervall that can rise towards it.)

The original Greek appears above each line, with a phonetic transcription below (with no intention of capturing eventual nuances of Pindar's dialect). As a convenient concordance between note sheet and heatmap, I have ensconsed all nine syllables with full 1 compatibility score (bright yellow) in boxes. 

Here's a word-for-word translation, enabling the greekless to still figure out at which words there is the most melodic movement: 

>Best is water, even though gold, shining fire // 

>alike, salient nightly, man-exalting outstanding wealth (i.e. outstanding like man-exalting wealth)


 ![Heatmap ol01 1-2](media/heatmaps/ol01_1-2.png)
![Notation ol01 1-2](media/ol01.svg)

<audio controls>
  <source src="media/ol01.mp3" type="audio/mpeg">
  Your browser does not support the audio element.
</audio>

# Why melodic compatibility?

A sizable part of the preserved Hellenistic musical fragments preserving songs set with Ancient Greek notation show marked compatibility between the direction of the musical intervals and the direction of the word pitch accents. The hypothesis is simply that at least some of pre-Hellenistic music, which is all lost[^2], showed this same tendency. 

That at least some archaic lyric songs were composed with the intention of minimizing clashes with the prosody, a rather modest claim, is supported by several arguments. Avoiding to get into a complicated and vexed general debate, I will here just summarize two of them. One is that it is untypical of artists of the Hellenistic era to make inventions *ex nihilo*, but highly typical to pick up, polish and push to the extreme tendencies already tentatively or partly present in the more organic culture of the earlier eras, such as Pindar. Another is that since the sense of Greek words depend on their intonation, it would be odd if composers, at least in cases with extraordinary risk of confusion, did not sometimes resort to incorporating and emphasizing the intended prosody of his words with his music.

[^1]: If the number of strophes is uneven, the lowest score is the smallest majority share, i.e. if there are 13 strophes, the lowest score is 7/13. 

[^2]: There are fragments of Euripides' tragedies set to music, but the papyri are Hellenistic and there is no way of knowing whether the melody is original or recomposed.

# The texts

It would be vain to look at the heatmaps without reading the actual odes. If the `text overlay` option above is not enough, all Pindar's odes are available in a readable format with the metre marked at David Chamberlain's excellent website [Hypotactic](https://hypotactic.com/latin/index.html?Use_Id=olympians). For those without knowledge of Greek, parallell English translations can be found at the [Perseus website](https://scaife.perseus.org/library/urn:cts:greekLit:tlg0033/), with the caveat that the syllables of the English translations do not (of course) stand in a one-to-one relationship with the Greek syllables, and cannot help decide the meaning at a certain position in the heatmap. For that, the reader would have to consult the relevant entry in the [Liddle and Scott online dictionary](https://logeion.uchicago.edu/%E1%BC%84%CF%81%CE%B9%CF%83%CF%84%CE%BF%CF%82).