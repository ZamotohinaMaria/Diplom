import sys, re, numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold, GroupKFold
from sklearn.metrics import roc_auc_score
sys.stdout.reconfigure(encoding='utf-8')

D = r'c:/Users/Marishka/Desktop/машушик/0 -ДИПЛОМ/0 - НИРС/Датасеты/'

def audit(name, seqs, y, hashes=None):
    print(f'\n######## {name}: n={len(seqs)}  pos={int(y.sum())}  neg={int((1-y).sum())}')
    L = np.array([len(s) for s in seqs])
    print('len: min/med/mean/max', L.min(), int(np.median(L)), round(L.mean(),1), L.max(), ' share len==max:', round((L==L.max()).mean(),3))
    vocab = set(t for s in seqs for t in s); print('vocab size', len(vocab))
    keys = [' '.join(s) for s in seqs]
    ser = pd.Series(keys)
    dup = ser.duplicated(keep=False)
    print('rows in duplicate-groups:', int(dup.sum()), f'({dup.mean():.1%});  unique seqs:', ser.nunique())
    df = pd.DataFrame({'k': keys, 'y': y})
    g = df.groupby('k')['y'].agg(['nunique', 'size'])
    print('seqs appearing in BOTH classes (label conflict):', int((g['nunique'] > 1).sum()))
    # leakage-aware: group split by identical sequence
    uniq = df.drop_duplicates('k')
    print('after dedup: n=', len(uniq), ' pos share', round(uniq.y.mean(), 3))
    # baselines
    for tag, d in [('raw rows', df), ('deduped', uniq)]:
        X = TfidfVectorizer(token_pattern=r'\S+', ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=False).fit_transform(d.k)
        cv = StratifiedKFold(5, shuffle=True, random_state=0)
        auc = cross_val_score(LogisticRegression(max_iter=2000), X, d.y, cv=cv, scoring='roc_auc')
        f1 = cross_val_score(LogisticRegression(max_iter=2000), X, d.y, cv=cv, scoring='f1')
        print(f'  TF-IDF(1-2gram)+LogReg 5fold [{tag}]  AUC={auc.mean():.4f}±{auc.std():.4f}  F1={f1.mean():.4f}')
    # unigram only, first-10 tokens only (shortcut check)
    X = TfidfVectorizer(token_pattern=r'\S+', lowercase=False).fit_transform([' '.join(s[:10]) for s in seqs])
    auc = cross_val_score(LogisticRegression(max_iter=2000), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring='roc_auc')
    print(f'  only FIRST 10 calls, unigram LogReg  AUC={auc.mean():.4f}')
    Xl = np.array([[len(s), len(set(s))] for s in seqs])
    auc = cross_val_score(LogisticRegression(max_iter=2000), Xl, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring='roc_auc')
    print(f'  only [length, n_unique_api] LogReg  AUC={auc.mean():.4f}')


# ---- MalBehavD-V1
m = pd.read_csv(r'c:/Users/Marishka/Desktop/code/Diplom/MalbehavD-V1-main/MalBehavD-V1-dataset.csv')
cols = [c for c in m.columns if re.fullmatch(r'\d+', str(c)) or str(c).startswith('Unnamed')]
seqs = [[str(v) for v in row if isinstance(v, str) and v != ''] for row in m[cols].values]
audit('MalBehavD-V1', seqs, m['labels'].values.astype(int))
print('sha256 unique:', m['sha256'].nunique(), 'of', len(m))

# ---- Kaggle (Oliveira-style)
k = pd.read_csv(D + 'Kaggle Malware Analysis Datasets API Call Sequences/dynamic_api_call_sequence_per_malware_100_0_306.csv')
tcols = [c for c in k.columns if c.startswith('t_')]
seqs = [[str(v) for v in row] for row in k[tcols].values]
audit('Kaggle Oliveira (per_malware_100_0_306)', seqs, k['malware'].values.astype(int))
print('hash unique:', k['hash'].nunique(), 'of', len(k))
