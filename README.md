
VarMap is a multiple omic level mapper (annotator) for genetic elements and genetic variations. It operates on genomic coordinates (e.g., `chr3:g.178936091G>A`) and transcript-dependent cDNA as well as protein coordinates (e.g., `PIK3CA:p.E545K` or `PIK3CA:c.1633G>A`, `NP_006266.2:p.G240Afs*50`). It is particularly designed with the functionality of resolving ambiguous mutation annotations arising from differential transcript usage. VarMap keeps awareness of the underlying unknown transcript structure (exon boundary, reference amino acid/base) while performing reverse annotation (via fuzzy matching from protein level to cDNA level).

We added some new features for variation transform which transvar does not support currently, and some functions (codes) were copied from transvar package!

1. Install
```bash
git clone https://github.com/Schaudge/varmap.git 
cd varmap && pip install .
```

2. Help
```bash
varmap -h 
```

3. Development
If you want develop (debug) from you local envirement, you can copy the share library (.so), which was build by install step, to the varmap directory!
e.g. 
```bash
cp tabix.cpython-*.so varmap/
cp _sswlib.cpython-*.so varmap/ssw/
```
then, configure a proper varmap.cfg in varmap directory, see an example setting in varmap/varmap.cfg!

