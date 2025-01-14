"""Process the raw EMO-DB dataset.

This assumes the file structure from the original compressed file:
/.../
    wav_corpus/
        *.wav
    silb/
        ...
    ...
"""

import shutil
from pathlib import Path

import click
from tqdm import tqdm

from ertk.dataset import write_annotations, write_filelist
from ertk.utils import PathlibPath

emotion_map = {
    "W": "anger",
    "L": "boredom",
    "E": "disgust",
    "A": "fear",
    "F": "happiness",
    "T": "sadness",
    "N": "neutral",
}


@click.command()
@click.argument("input_dir", type=PathlibPath(exists=True, file_okay=False))
def main(input_dir: Path):
    """Process the EMO-DB dataset at location INPUT_DIR."""
    paths = list(input_dir.glob("wav_corpus/*.wav"))
    write_annotations({p.stem: emotion_map[p.stem[5]] for p in paths}, "label")
    speaker_dict = {p.stem: p.stem[:2] for p in paths}
    write_annotations(speaker_dict, "speaker")
    male_speakers = ["03", "10", "11", "12", "15"]
    gender_dict = {
        k: "M" if v in male_speakers else "F" for k, v in speaker_dict.items()
    }
    write_annotations(gender_dict, "gender")
    write_annotations({p.stem: "de" for p in paths}, "language")
    Path("resampled").mkdir(exist_ok=True)
    for p in tqdm(paths, desc="Copying audio"):
        shutil.copyfile(p, Path("resampled", p.name))
    write_filelist(Path("resampled").glob("*.wav"), "files_all")


if __name__ == "__main__":
    main()
