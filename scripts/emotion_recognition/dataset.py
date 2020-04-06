import re
from collections import Counter, namedtuple
from pathlib import Path
from typing import Union

import arff
import netCDF4
import numpy as np
import pandas as pd
import soundfile
from sklearn.preprocessing import StandardScaler, label_binarize

from .binary_arff import decode as decode_arff

__all__ = [
    'UtteranceDataset',
    'FrameDataset',
    'RawDataset',
    'parse_regression_annotations',
    'parse_classification_annotations',
    'corpora'
]

Corpus = namedtuple(
    'Corpus',
    ['emotion_map', 'arousal_map', 'valence_map', 'male_speakers',
     'female_speakers', 'speakers', 'get_emotion', 'get_speaker']
)

corpora = {
    'cafe': Corpus(
        {
            'C': 'anger',
            'D': 'disgust',
            'J': 'happiness',
            'N': 'neutral',
            'P': 'fear',
            'S': 'surprise',
            'T': 'sadness'
        },
        None,
        None,
        ['01', '03', '05', '07', '09', '11'],
        ['02', '04', '06', '08', '10', '12'],
        None,
        lambda n: n[3],
        lambda n: n[:2]
    ),
    'crema-d': Corpus(
        {
            'A': 'anger',
            'D': 'disgust',
            'F': 'fear',
            'H': 'happy',
            'S': 'sad',
            'N': 'neutral',
        },
        None,
        None,
        None,
        None,
        [
            '1042', '1070', '1030', '1087', '1061', '1086', '1026', '1017',
            '1039', '1082', '1032', '1015', '1062', '1012', '1046', '1010',
            '1014', '1064', '1080', '1023', '1056', '1066', '1035', '1074',
            '1068', '1027', '1043', '1065', '1076', '1060', '1019', '1011',
            '1075', '1008', '1006', '1025', '1053', '1058', '1085', '1069',
            '1024', '1084', '1033', '1054', '1090', '1013', '1038', '1072',
            '1036', '1088', '1071', '1005', '1057', '1029', '1020', '1073',
            '1050', '1007', '1031', '1003', '1002', '1079', '1040', '1047',
            '1077', '1078', '1049', '1051', '1041', '1052', '1083', '1016',
            '1034', '1009', '1055', '1048', '1018', '1091', '1045', '1022',
            '1004', '1089', '1067', '1059', '1063', '1001', '1021', '1028',
            '1044', '1037', '1081'
        ],
        None,
        lambda n: n[:4]
    ),
    'demos': Corpus(
        {
            'rab': 'anger',
            'tri': 'sadness',
            'gio': 'happiness',
            'pau': 'fear',
            'dis': 'disgust',
            'col': 'guilt',
            'sor': 'surprise'
        },
        {
            'negative': ['disgust', 'neutral', 'sadness', 'guilt'],
            'positive': ['anger', 'fear', 'happiness', 'surprise']
        },
        {
            'negative': ['anger', 'guilt', 'disgust', 'fear', 'sadness'],
            'positive': ['happiness', 'neutral', 'surprise']
        },
        [
            '02', '03', '04', '05', '08', '09', '10', '11', '12', '14', '15',
            '16', '18', '19', '23', '24', '25', '26', '27', '28', '30', '33',
            '34', '39', '41', '50', '51', '52', '53', '58', '59', '63', '64',
            '65', '66', '67', '68', '69'
        ],
        [
            '01', '17', '21', '22', '29', '31', '36', '37', '38', '40', '43',
            '45', '46', '47', '49', '54', '55', '56', '57', '60', '61'
        ],
        None,
        lambda n: n[-6:-3],
        lambda n: n[-9:-7]
    ),
    'emodb': Corpus(
        {
            'W': 'anger',
            'L': 'boredom',
            'E': 'disgust',
            'A': 'fear',
            'F': 'happiness',
            'T': 'sadness',
            'N': 'neutral'
        },
        {
            'negative': ['boredom', 'disgust', 'neutral', 'sadness'],
            'positive': ['anger', 'fear', 'happiness']
        },
        {
            'negative': ['anger', 'boredom', 'disgust', 'fear', 'sadness'],
            'positive': ['happiness', 'neutral']
        },
        ['03', '10', '11', '12', '15'],
        ['08', '09', '13', '14', '16'],
        None,
        lambda n: n[5],
        lambda n: n[:2]
    ),
    'emofilm': Corpus(
        {
            'ans': 'fear',
            'dis': 'disgust',
            'gio': 'happiness',
            'rab': 'anger',
            'tri': 'sadness'
        },
        None,
        None,
        None,
        None,
        ['en', 'es', 'it'],
        lambda n: n[2:5],
        lambda n: n[-2:]
    ),
    'enterface': Corpus(
        {
            'an': 'anger',
            'di': 'disgust',
            'fe': 'fear',
            'ha': 'happiness',
            'sa': 'sadness',
            'su': 'surprise'
        },
        {
            'negative': ['disgust', 'sadness'],
            'positive': ['anger', 'fear', 'happiness', 'surprise']
        },
        {
            'negative': ['anger', 'disgust', 'fear', 'sadness'],
            'positive': ['happiness', 'surprise']
        },
        None,
        None,
        ['s' + str(i) for i in range(1, 45) if i != 6],
        lambda n: n[-4:-2],
        lambda n: n[:n.find('_')]
    ),
    'iemocap': Corpus(
        {
            'ang': 'anger',
            'hap': 'happiness',
            'sad': 'sadness',
            'neu': 'neutral'
        },
        None,
        None,
        ['01M', '02M', '03M', '04M', '05M'],
        ['01F', '02F', '03F', '04F', '05F'],
        None,
        lambda n: n[-3:],
        lambda n: n[3:6]
    ),
    'jl': Corpus(
        {
            'angry': 'angry',
            'sad': 'sad',
            'neutral': 'neutral',
            'happy': 'happy',
            'excited': 'excited'
        },
        None,
        None,
        ['male1', 'male2'],
        ['female1', 'female2'],
        None,
        lambda n: re.match(r'^\w+\d_([a-z]+)_.*$', n).group(1),
        lambda n: n[:n.find('_')]
    ),
    'msp-improv': Corpus(
        {
            'A': 'angry',
            'H': 'happy',
            'S': 'sad',
            'N': 'neutral'
        },
        None,
        None,
        ['M01', 'M02', 'M03', 'M04', 'M05', 'M06'],
        ['F01', 'F02', 'F03', 'F04', 'F05', 'F06'],
        None,
        lambda n: n[-1],
        lambda n: n[5:8]
    ),
    'portuguese': Corpus(
        {
            'angry': 'angry',
            'disgust': 'disgust',
            'fear': 'fear',
            'happy': 'happy',
            'sad': 'sad',
            'neutral': 'neutral',
            'surprise': 'surprise'
        },
        None,
        None,
        None,
        None,
        ['A', 'B'],
        lambda n: re.match(r'^\d+[sp][AB]_([a-z]+)\d+$', n).group(1),
        lambda n: n[n.find('_') - 1]
    ),
    'ravdess': Corpus(
        {
            '01': 'neutral',
            '02': 'calm',
            '03': 'happy',
            '04': 'sad',
            '05': 'angry',
            '06': 'fearful',
            '07': 'disgust',
            '08': 'surprised'
        },
        None,
        None,
        ['{:02d}'.format(i) for i in range(1, 25, 2)],
        ['{:02d}'.format(i) for i in range(2, 25, 2)],
        None,
        lambda n: n[6:8],
        lambda n: n[-2:]
    ),
    'savee': Corpus(
        {
            'a': 'anger',
            'd': 'disgust',
            'f': 'fear',
            'h': 'happiness',
            'n': 'neutral',
            'sa': 'sadness',
            'su': 'suprise'
        },
        {
            'negative': ['disgust', 'neutral', 'sadness'],
            'positive': ['anger', 'fear', 'happiness', 'surprise']
        },
        {
            'negative': ['anger', 'disgust', 'fear', 'sadness'],
            'positive': ['happiness', 'neutral', 'surprise']
        },
        None,
        None,
        ['DC', 'JE', 'JK', 'KL'],
        lambda n: n[3] if n[4].isdigit() else n[3:5],
        lambda n: n[:2]
    ),
    'semaine': Corpus(
        {},
        None,
        None,
        None,
        None,
        ['{:02d}'.format(i) for i in range(1, 25) if i not in [7, 8]],
        None,
        lambda n: n[:2]
    ),
    'shemo': Corpus(
        {
            'A': 'anger',
            'H': 'happiness',
            'N': 'neutral',
            'S': 'sadness',
            'W': 'surprise'
        },
        None,
        None,
        ['M{:02d}'.format(i) for i in range(1, 57)],
        ['F{:02d}'.format(i) for i in range(1, 32)],
        None,
        lambda n: n[3],
        lambda n: n[:3]
    ),
    'smartkom': Corpus(
        {
            'Neutral': 'neutral',
            'Freude_Erfolg': 'joy',
            'Uberlegen_Nachdenken': 'pondering',
            'Ratlosigkeit': 'helpless',
            'Arger_Miserfolg': 'anger',
            'Uberraschung_Verwunderung': 'surprise',
            'Restklasse': 'unknown'
        },
        None,
        None,
        None,
        None,
        [
            'AAA', 'AAB', 'AAC', 'AAD', 'AAE', 'AAF', 'AAG', 'AAH', 'AAI',
            'AAJ', 'AAK', 'AAL', 'AAM', 'AAN', 'AAO', 'AAP', 'AAQ', 'AAR',
            'AAS', 'AAT', 'AAU', 'AAV', 'AAW', 'AAX', 'AAY', 'AAZ', 'ABA',
            'ABB', 'ABC', 'ABD', 'ABE', 'ABF', 'ABG', 'ABH', 'ABI', 'ABJ',
            'ABK', 'ABL', 'ABM', 'ABN', 'ABO', 'ABP', 'ABQ', 'ABR', 'ABS',
            'AIS', 'AIT', 'AIU', 'AIV', 'AIW', 'AIX', 'AIY', 'AIZ', 'AJA',
            'AJB', 'AJC', 'AJD', 'AJE', 'AJF', 'AJG', 'AJH', 'AJI', 'AJJ',
            'AJK', 'AJL', 'AJM', 'AJN', 'AJO', 'AJP', 'AJQ', 'AJR', 'AJS',
            'AJT', 'AJU', 'AJV', 'AJW', 'AJX', 'AJY', 'AJZ', 'AKA', 'AKB',
            'AKC', 'AKD', 'AKE', 'AKF', 'AKG'
        ],
        None,
        lambda n: n[8:11]
    ),
    'tess': Corpus(
        {
            'angry': 'angry',
            'disgust': 'disgust',
            'fear': 'fear',
            'happy': 'happy',
            'ps': 'surprise',
            'sad': 'sad',
            'neutral': 'neutral'
        },
        None,
        None,
        None,
        None,
        ['OAF', 'YAF'],
        lambda n: n[n.rfind('_') + 1:],
        lambda n: n[:3]
    )
}

for corpus in corpora:
    if (corpora[corpus].male_speakers is not None
            and corpora[corpus].female_speakers is not None):
        corpora[corpus] = corpora[corpus]._replace(
            speakers=(corpora[corpus].male_speakers
                      + corpora[corpus].female_speakers))


def parse_regression_annotations(file):
    df = pd.read_csv(file, index_col=0)
    annotations = df.to_dict(orient='index')
    return annotations


def parse_classification_annotations(file):
    df = pd.read_csv(file, index_col=0)
    annotations = df.to_dict()[df.columns[0]]
    return annotations


class Dataset():
    def __init__(self, corpus: str, normaliser=StandardScaler(),
                 normalise_method: str = 'speaker', binarise: bool = False):
        if corpus not in corpora:
            raise NotImplementedError(
                "Corpus {} hasn't been implemented yet.".format(corpus))
        self.corpus = corpus

        self.classes = list(corpora[self.corpus].emotion_map.values())
        self.class_to_int = {c: self.classes.index(c) for c in self.classes}
        self.n_classes = len(self.classes)

        self.n_instances = len(self.names)
        self.n_features = len(self.features)

        self.normaliser = normaliser
        self.normalise_method = normalise_method

        self.speakers = corpora[self.corpus].speakers
        self.n_speakers = len(self.speakers)
        self.sp_get = corpora[self.corpus].get_speaker
        self.speaker_indices = np.array(
            [self.speakers.index(self.sp_get(n)) for n in self.names],
            dtype=int
        )

        if self.corpus == 'iemocap':
            speaker_indices_to_group = np.array(
                [0, 1, 2, 3, 4, 0, 1, 2, 3, 4])
            self.speaker_group_indices = speaker_indices_to_group[
                self.speaker_indices]
        elif self.corpus == 'msp-improv':
            speaker_indices_to_group = np.array(
                [0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5])
            self.speaker_group_indices = speaker_indices_to_group[
                self.speaker_indices]
        else:
            self.speaker_group_indices = self.speaker_indices

        self.gender_indices = {'all': np.arange(self.n_instances)}
        if (corpora[self.corpus].male_speakers is not None
                and corpora[self.corpus].female_speakers):
            self.male_speakers = corpora[self.corpus].male_speakers
            self.female_speakers = corpora[self.corpus].female_speakers
            self.m_indices = np.array([i for i in range(self.n_instances)
                                       if self.sp_get(self.names[i])
                                       in self.male_speakers], dtype=int)
            self.f_indices = np.array([i for i in range(self.n_instances)
                                       if self.sp_get(self.names[i])
                                       in self.female_speakers], dtype=int)
            self.gender_indices['m'] = self.m_indices
            self.gender_indices['f'] = self.f_indices

        self.create_data()
        self.labels = {'all': self.y}
        if binarise:
            self.binary_y = label_binarize(self.y, np.arange(self.n_classes))
            self.labels.update(
                {c: self.binary_y[:, c] for c in range(self.n_classes)})

            if (corpora[corpus].arousal_map is not None
                    and corpora[corpus].valence_map is not None):
                print("Binarising arousal and valence")
                class_arousal = corpora[corpus].arousal_map
                arousal_map = np.array([
                    1 if c in class_arousal['positive'] else 0
                    for c in self.classes
                ])
                class_valence = corpora[corpus].valence_map
                valence_map = np.array([
                    1 if c in class_valence['positive'] else 0
                    for c in self.classes
                ])
                self.arousal_y = np.array(arousal_map[self.y.astype(int)],
                                          dtype=np.float32)
                self.valence_y = np.array(valence_map[self.y.astype(int)],
                                          dtype=np.float32)
                self.labels['arousal'] = self.arousal_y
                self.labels['valence'] = self.valence_y

        print('Corpus: {}'.format(corpus))
        print('Classes: {} {}'.format(self.n_classes, tuple(self.classes)))
        print('{} speakers'.format(len(self.speakers)))
        print('Normalisation function: {}'.format(self.normaliser.__class__))
        print('Normalise method: {}'.format(self.normalise_method))
        print()

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]

    def create_data(self):
        return NotImplementedError()


class NetCDFDataset(Dataset):
    def __init__(self, file: Union[Path, str], corpus: str,
                 normaliser=StandardScaler(),
                 normalise_method: str = 'speaker', binarise: bool = False):
        self.file = Path(file)
        self.dataset = dataset = netCDF4.Dataset(str(self.file))
        self.names = [Path(f).stem for f in dataset.variables['filename']]
        self.features = ['representation_{}'.format(i + 1)
                         for i in range(dataset.dimensions['generated'].size)]

        super().__init__(corpus, normaliser=normaliser,
                         normalise_method=normalise_method, binarise=binarise)

        print('{} instances x {} features'.format(self.n_instances,
                                                  self.n_features))
        speakers, counts = np.unique([self.sp_get(n) for n in self.names],
                                     return_counts=True)
        print("Speaker counts:")
        print(' '.join([format(s, '<5s') for s in speakers]))
        print(' '.join([format(x, '<5d') for x in counts]))

        self.dataset.close()
        del self.dataset

    def create_data(self):
        self.x = np.array(self.dataset.variables['features'])
        self.y = np.empty(self.n_instances, dtype=np.float32)

        annotations = parse_classification_annotations(
            self.file.parent.parent / 'labels.csv')
        for i, name in enumerate(self.names):
            emotion = annotations[name]
            self.y[i] = self.class_to_int[emotion]
        sort = np.argsort(self.names)
        self.x = self.x[sort]
        self.y = self.y[sort]
        self.names = [self.names[i] for i in sort]


class RawDataset(Dataset):
    def __init__(self, file, corpus, normaliser=StandardScaler(),
                 normalise_method='speaker', binarise=False):
        self.features = ['pcm']

        self.file = file

        self.names = []
        self.filenames = []
        with open(file) as fid:
            for line in fid:
                filename = line.strip()
                self.filenames.append(filename)
                name = Path(filename).stem
                self.names.append(name)

        super().__init__(corpus, normaliser=normaliser,
                         normalise_method=normalise_method, binarise=binarise)

        print("{} audio files".format(self.n_instances))

        del self.filenames

    def create_data(self):
        self.x = np.empty(self.n_instances, dtype=object)
        self.y = np.empty(self.n_instances, dtype=np.float32)
        for i, filename in enumerate(self.filenames):
            audio, sr = soundfile.read(filename, dtype=np.float32)
            audio = np.expand_dims(audio, axis=1)
            self.x[i] = audio

            annotations = parse_classification_annotations(
                Path(self.file).parent / 'labels.txt')
            name = Path(filename).stem
            emotion = annotations[name]
            self.y[i] = self.class_to_int[emotion]


class ArffDataset(Dataset):
    def __init__(self, path, normaliser=StandardScaler(),
                 normalise_method='speaker', binarise=False):
        path = Path(path)
        if path.suffix == '.bin':
            with open(path, 'rb') as fid:
                data = decode_arff(fid)
        else:
            with open(path) as fid:
                data = arff.load(fid)

        self.raw_data = data['data']
        self.names = [x[0] for x in self.raw_data]
        self.features = [x[0] for x in data['attributes'][1:-1]]

        corpus = data['relation']
        super().__init__(corpus, normaliser=normaliser,
                         normalise_method=normalise_method, binarise=binarise)

        del self.raw_data

    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]

    def create_data(self):
        self.x = np.empty((self.n_instances, self.n_features),
                          dtype=np.float32)
        self.y = np.empty(self.n_instances, dtype=np.float32)
        for i, inst in enumerate(self.raw_data):
            self.x[i, :] = inst[1:-1]
            self.y[i] = self.class_to_int[inst[-1]]

        if self.normalise_method == 'all':
            self.x = self.normaliser.fit_transform(self.x)
        elif self.normalise_method == 'speaker':
            for sp in range(len(self.speakers)):
                idx = self.speaker_indices == sp
                self.x[idx] = self.normaliser.fit_transform(self.x[idx])


class UtteranceDataset(ArffDataset):
    def __init__(self, path, normaliser=StandardScaler(),
                 normalise_method='speaker', binarise=False):
        super().__init__(path, normaliser=StandardScaler(),
                         normalise_method='speaker', binarise=binarise)

        print('{} instances x {} features'.format(self.n_instances,
                                                  self.n_features))
        speakers, counts = np.unique([self.sp_get(n) for n in self.names],
                                     return_counts=True)
        print("Speaker counts:")
        print(' '.join([format(s, '<5s') for s in speakers]))
        print(' '.join([format(x, '<5d') for x in counts]))


class FrameDataset(ArffDataset):
    def __init__(self, path, normaliser=StandardScaler(),
                 normalise_method='speaker', binarise=False):
        super().__init__(path, normaliser=normaliser,
                         normalise_method=normalise_method, binarise=binarise)

        names = Counter(self.names)  # Ordered by insertion in Python 3.7+
        self.names = list(names.keys())
        self.n_instances = len(self.names)

        idx = np.cumsum([0] + list(names.values()))
        self.speaker_indices = self.speaker_indices[idx[:-1]]
        if hasattr(self, 'speaker_group_indices'):
            self.speaker_group_indices = self.speaker_group_indices[idx[:-1]]
        self.gender_indices = {'all': np.arange(self.n_instances)}

        self.x = np.array([self.x[idx[i]:idx[i + 1]]
                           for i in range(self.n_instances)], dtype=object)
        self.y = self.y[idx[:-1]]

        self.labels = {'all': self.y}
        if binarise:
            self.labels.update({c: self.binary_y[:, c]
                                for c in range(self.n_classes)})

        print("{} sequences of vectors of size {}".format(self.n_instances,
                                                          self.n_features))

    def pad_arrays(self, pad: int = 32):
        for i in range(len(self.x)):
            x = self.x[i]
            padding = int(np.ceil(x.shape[0] / pad)) * pad - x.shape[0]
            self.x[i] = np.pad(x, ((0, padding), (0, 0)))