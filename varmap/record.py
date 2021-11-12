"""
The MIT License

Copyright (c) 2015
The University of Texas MD Anderson Cancer Center
Wanding Zhou, Tenghui Chen, Ken Chen (kchen3@mdanderson.org)

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import re, sys
from .faidx import *
from .utils import *
from .err import *
import locale
locale.setlocale(locale.LC_ALL, '')

class Pos():

    def __init__(self, pos='', tpos=0):

        self.pos = pos # self.pos < 0 is for end of the coding sequence
        # respect to exon boundary, non-zero value indicates the position is relative to exon boundary
        self.tpos = tpos

    def __repr__(self):
        if self.tpos < 0:
            return '%s%d' % (str(self.pos), self.tpos)
        elif self.tpos > 0:
            if self.pos < 0:
                return '*%d' % self.tpos
            else:
                return '%s+%d' % (str(self.pos), self.tpos)
        else:
            return str(self.pos)

    def __eq__(self, other):
        if (self.pos == other.pos and
            self.tpos == other.tpos):
            return True
        else:
            return False

    def add(self, inc):
        """ doesn't check boundary, may overflow """

        if self.tpos == 0:
            self.pos += inc
        else:
            self.tpos += inc

    def subtract(self, inc):
        """ doesn't check boundary, may overflow """

        if self.tpos == 0:
            self.pos -= inc
        else:
            self.tpos -= inc

    def included_plus(self):
        if self.tpos > 0:
            return self.pos + 1
        else:
            return self.pos

    def included_minus(self):
        if self.tpos < 0:
            return self.pos - 1
        else:
            return self.pos

def same_intron(p1, p2):

    if ((p1.included_minus() == p2.included_minus()) and
        (p1.tpos != 0) and (p2.tpos != 0)):
        return True
    else:
        return False

def append_inf(f, a):
    if f:
        return f+';'+a
    else:
        return a

class RegAnno():

    """ annotating a single site
    generated by Transcript.describe()
    """

    def __init__(self):
        self.exonic = False
        self.exon = None
        self.cds = False        # whether in CDS
        self.UTR = None         # '3' or '5'

        self.intronic = False
        self.intron_exon1 = None
        self.intron_exon2 = None

        self.cds_beg = None     # if site hits CDS start
        self.cds_end = None     # if site hits CDS end

    def __repr__(self):

        return '<RegAnno: exon: %s intronic: %s>' % (self.exonic, self.intronic)

    def genic(self):

        if hasattr(self, "intergenic"):
            return False
        else:
            return True

    def entirely_in_cds(self):

        return self.cds

    def csqn(self):
        """ generate csqn based on region, this gets called
        usually when there is no amino acid change """
        if self.intronic:
            return "Intronic"
        if self.UTR:
            return "%s-UTR" % self.UTR
        if hasattr(self, "intergenic"):
            return "Intergenic"
        return "Unclassified"

    def format0(self, with_name=False):

        if hasattr(self, 'intergenic'):
            # self.intergenic - RegIntergenicAnno
            return self.intergenic.format0()
        else:
            f = ''
            if self.UTR:
                f = append_inf(f, '%s-UTR' % self.UTR)

            # if hasattr(self, 'promotor') and self.promotor:
            #     f = append_inf(f, 'promotor')

            if self.intronic:
                f = append_inf(f, 'intron_between_exon_%d_and_%d' %
                               (self.intron_exon1, self.intron_exon2))
            elif self.exonic:
                if self.cds:
                    f = append_inf(f, 'cds_in_exon_%d' % self.exon)
                else:
                    f = append_inf(f, 'noncoding_exon_%d' % self.exon)
            if with_name:
                f = append_inf(f, self.t.gene_name)
            return f

    def format(self, with_name=False):
        return 'inside_[%s]' % self.format0(with_name)

def format_group(d):
    return locale.format('%d', d, grouping=False)

class RegIntergenicAnno():

    """ annotating a single intergenic site """

    def __init__(self):

        self.e5_name = None
        self.e5_dist = None
        self.e5_strand = None

        self.e3_name = None
        self.e3_dist = None
        self.e3_strand = None

    def e5_stream(self):
        if self.e5_strand is None:
            return None
        elif self.e5_strand == '+':
            return 'downstream'
        else:
            return 'upstream'

    def e3_stream(self):
        if self.e3_strand is None:
            return None
        elif self.e3_strand == '-':
            return 'downstream'
        else:
            return 'upstream'

    def format0(self):

        return "intergenic_between_%s(%s)_and_%s(%s)" % (
            self.e5_name,
            '%s_bp' % format_group(self.e5_dist) if self.e5_strand is None
            else '%s_bp_%s' % (format_group(self.e5_dist), self.e5_stream()),
            self.e3_name,
            '%s_bp' % format_group(self.e3_dist) if self.e3_strand is None
            else '%s_bp_%s' % (format_group(self.e3_dist), self.e3_stream()))

    def format(self):

        return 'inside_[%s]' % (self.format0(),)

def same_region(r1, r2):

    return ((r1.format() == r2.format()) and
            ((not hasattr(r1,'t')) or (not hasattr(r2,'t')) or r1.t == r2.t))

class RegCDSAnno():

    """ Annotation of a region or a site in codon level
    rather than nucleotide level used in annotating
    protein regions/sites/changes
    """

    def __init__(self, t, codon=None):
        self.exons = []
        self.t = t
        if codon is not None:
            self.from_codon(codon)

    def from_codon(self, c):
        self.exons = self.t._tnuc_range2exon_inds(c.index*3-2, c.index*3)

    def from_cindex(self, ci):
        self.exons = self.t._tnuc_range2exon_inds(ci*3-2, ci*3)

    def from_taa_range(self, taa_beg, taa_end):
        self.exons = self.t._tnuc_range2exon_inds(taa_beg*3-2, taa_end*3)

    def format0(self):

        s = ''
        if len(self.exons) == 1:
            s = append_inf(s, 'cds_in_exon_%s' % str(self.exons[0]))
        else:
            s = append_inf(s, 'cds_in_exons_[%s]' % ','.join(map(str, self.exons)))

        return s

    def format(self):

        return 'inside_[%s]' % self.format0()

class RegSpanAnno():

    """ annotation of a span
    generated by Transcript.describe_span()
    """

    def __init__(self): #, long_range=False):

        # self.whole_gene = False
        self.b1 = None         # boundary 1, an object of RegAnno
        self.b2 = None         # boundary 2, an object of RegAnno
        # self.transcript_regs = [] # covered parts of a transcript
        # self.genes = []
        # self.long_range = long_range
        self.spanning = []

    def in_UTR(self):

        return (self.b1.UTR and self.b2.UTR and self.b1.UTR == self.b2.UTR)

    def in_exon(self):
        return (self.b1.exonic and
                self.b2.exonic and
                self.b1.exon == self.b2.exon)

    def entirely_in_cds(self):
        return (self.b1.cds and
                self.b2.cds and
                self.b1.exon == self.b2.exon)

    def in_intron(self):

        return (self.b1.intronic and
                self.b2.intronic and
                self.b1.intron_exon1 == self.b2.intron_exon1 and
                self.b1.intron_exon2 == self.b2.intron_exon2)

    # def intergenic(self):

    #     return (hasattr(self.b1, 'intergenic') and
    #             hasattr(self.b2, 'intergenic') and
    #             self.b1.intergenic[1] == self.b2.intergenic[1])

    def csqn(self):
        """ generate csqn based on region, this gets called
        usually when there is no amino acid change """

        # TODO: check if the span is large and cover many splice sites.
        if hasattr(self, 'intergenic') and len(self.intergenic.spanning) == 0:
            return "Intergenic"
        if hasattr(self, 'splice_donors') and len(self.splice_donors) > 0:
            return "SpliceDonor"
        if hasattr(self, 'splice_acceptors') and len(self.splice_acceptors) > 0:
            return "SpliceAcceptor"
        if self.in_intron():
            return "Intronic"
        if self.in_UTR():
            return "%s-UTR" % self.b1.UTR
        return "Unclassified"

    def format(self):

        if hasattr(self, 'intergenic'):
            return self.intergenic.format()

        if same_region(self.b1, self.b2):
            return 'inside_[%s]' % (self.b1.format0(),)
        else:                   # large region
            if hasattr(self.b1, 't') and hasattr(self.b2, 't') and self.b1.t == self.b2.t:
                s = 'from_[%s]_to_[%s]' % (self.b1.format0(), self.b2.format0())
            else:
                s = 'from_[%s]_to_[%s]' % (self.b1.format0(with_name=True),
                                           self.b2.format0(with_name=True))
            if len(self.spanning) > 0:
                if len(self.spanning) <= 5:
                    s += '_spanning_[%s]' % ','.join([g.name for g in self.spanning])
                else:
                    s += '_spanning_[%d_genes]' % len(self.spanning)

            return s

        # f = ''
        # if self.long_range:
        #     ff = 'covering_%d_genes' % (len(genes),)
        #     if len(self.genes) <= 5:
        #         ff = '(%s)' % ','.join([g.name for g in genes])
        #     f = append_inf(f, ff)

        # if self.in_UTR():
        #     f = append_inf(f, '%s-UTR' % self.b1.UTR)

        # if self.in_exon():
        #     if self.b1.cds and self.b2.cds:
        #         f = append_inf(f, 'CDS_%d' % self.b1.exon)
        #     else:
        #         f = append_inf(f, 'Exonic_%d' % self.b1.exon)

        # elif self.in_intron():
        #     f = append_inf(f, self.b1.format())
        #     # f = append_inf(f, 'Intronic_%d_%d' %
        #     #                (self.b1.intron_exon1, self.b1.intron_exon2))

        # elif self.intergenic():
        #     f = append_inf(f, 'intergenic_%s' % self.b1.intergenic)

        # else:
        #     f = append_inf(f, 'from_[%s]_to_[%s]' % (self.b1.format(), self.b2.format()))

        # return f

class SpliceSite():

    def __init__(self):
        self.chrm   = "chrNA"
        self.pos    = -1
        self.exonno = -1    # exon number
        self.stype  = "Donor"
        # whether only next to splice site from the exon side (splice site is on the intron side)
        self.nextto = False

    def format(self):
        s = ''
        if self.nextto:
            s += 'NextTo'
        s += 'Splice%sOfExon%d_At_%s:%d' % (self.stype, self.exonno, self.chrm, self.pos)
        return s

def parse_pos(posstr):

    if posstr.isdigit():
        p = Pos()
        p.pos = int(posstr)
        p.tpos = 0
        return p

    m = re.match(r'(\d+)([+\-0-9]+)', posstr)
    if m:
        p = Pos()
        p.pos = int(m.group(1))
        p.tpos = eval(m.group(2))
        return p

    m = re.match(r'([*+\-0-9]+)', posstr)
    if m:
        p = Pos()
        if m.group(1)[0] == '-':
            p.pos = 1
        else:
            p.pos = -1          # '+'/'*' for END of transcript
        tpos = m.group(1)
        if tpos[0] == '*':      # strip '*'
            tpos = tpos[1:]
        p.tpos = eval(tpos)
        return p

    raise InvalidInputError('invalid_position_string_%s' % posstr)

class Query(object):

    def __init__(self):

        """ for a region by default, no mutation information included """
        self.beg = ''
        self.end = ''
        self.op = None
        self.is_codon = True
        self.gn_name = None
        self.tpt = ''
        self.tpt_version = None
        self.msg = ''
        self.tok = None         # by default, is a failed query

    def set_pos(self, pos_str):

        if (pos_str.isdigit() and int(pos_str) > 0):
            self.pos = int(pos_str)
            return True
        else:
            err_warn('abnormal position %s. skip.' % pos_str)
            return False


class QueryGENE(Query):

    def __init__(self):

        super(QueryGENE, self).__init__()
        self.gene = ''

class QueryREG(Query):

    def __init__(self):

        super(QueryREG, self).__init__()
        self.beg = ''
        self.end = ''
        self.refseq = ''

class QuerySNV(Query):

    def __init__(self):

        super(QuerySNV, self).__init__()
        self.pos = ''
        self.ref = ''
        self.alt = ''

class QueryDEL(Query):

    def __init__(self):

        super(QueryDEL, self).__init__()
        self.beg = ''
        self.end = ''
        self.delseq = ''
        # for amino acid
        self.beg_aa = ''
        self.end_aa = ''

class QueryFrameShift(Query):

    def __init__(self):

        super(QueryFrameShift, self).__init__()
        self.pos = None
        self.ref = ''
        self.alt = ''
        self.stop_index = ''

class QueryINS(Query):

    def __init__(self):

        super(QueryINS, self).__init__()
        self.pos = ''           # position of base before
        self.insseq = ''
        # for amino acid level query
        self.beg = ''
        self.beg_aa = ''
        self.end = ''
        self.end_aa = ''

class QueryMNV(Query):

    def __init__(self):

        super(QueryMNV, self).__init__()
        self.beg = ''
        self.beg_aa = ''
        self.end = ''
        self.end_aa = ''
        self.refseq = ''
        self.altseq = ''

class QueryDUP(Query):

    def __init__(self):

        super(QueryDUP, self).__init__()
        self.beg = ''
        self.beg_aa = ''
        self.end = ''
        self.end_aa = ''
        self.dupseq = ''


def normalize_reg(q):

    """ create a sensable region
    respect to the length of the chromosome """

    if q.beg > reflen(q.tok):
        err_warn('region beg %d greater than chromosome length %d, truncated.' % (q.beg, reflen(q.tok)))
        q.beg = reflen(q.tok)

    if q.end > reflen(q.tok):
        err_warn('region end %d greater than chromosome length %d, truncated.' % (q.end, reflen(q.tok)))
        q.end = reflen(q.tok)
    if q.beg < 0:
        err_warn('region beg %d negative, truncated to 0.')
        q.beg = 0
    if q.end < 0:
        err_warn('region end %d negative, truncated to 0.')
        q.end = 0

template = "{r.tname}\t{r.gene}\t{r.strand}\t{gnuc}/{tnuc}/{taa}\t{reg}\t{r.info}"
def print_header_s():
    return 'transcript\tgene\tstrand\tcoordinates(gDNA/cDNA/protein)\tregion\tinfo'

def print_header(args):
    s = 'input\t'+print_header_s()
    if args.gseq:
        s += '\tCHROM\tPOS\tREF\tALT'
    return s

class Record():

    def __init__(self, is_var=False):

        self.tname = '.'        # transcript name
        self.chrm = '.'         # genomic chromosome
        self.gene = '.'
        self.strand = '.'
        self.reg = '.'          # region
        self.info = '.'         # ;-separated key=value pair
        self.is_var = is_var    # whether the record is for a variant
        self.csqn = []

    def tnuc(self):
        """ format in HGVS nomenclature e.g., c.12345A>T """
        s = 'c.'
        if hasattr(self, 'tnuc_range') and self.tnuc_range:
            s += self.tnuc_range
            if s == 'c.': return '.'
        else:
            if hasattr(self, 'tnuc_pos') and self.tnuc_pos: s += str(self.tnuc_pos)
            if hasattr(self, 'tnuc_ref') and self.tnuc_ref: s += self.tnuc_ref
            s += '>'
            if hasattr(self, 'tnuc_alt') and self.tnuc_alt: s += self.tnuc_alt
            if s == 'c.>': return '.'
        return s

    def prepend_info(self, app):
        if self.info and self.info != ".":
            self.info = app+";"+self.info
        else:
            self.info = app

    def append_info(self, app):
        if self.info and self.info != '.':
            self.info += ';'+app
        else:
            self.info = app

    def set_promoter(self):

        if isinstance(self.reg, RegAnno):
            if hasattr(self.reg, 'promoter'):
                if self.reg.promoter:
                    for t in self.reg.promoter:
                        self.append_info('promoter_region_of_[%s]' % t.gene_name)

        if isinstance(self.reg, RegSpanAnno):
            if hasattr(self.reg, 'promoter'):
                if self.reg.promoter:
                    for t, overlap, frac in self.reg.promoter:
                        self.append_info('promoter_region_of_[%s]_overlaping_%d_bp(%1.2f%%)'
                                         % (t.gene_name, overlap, frac))

    def set_splice(self, action='', csqn_action=''):

        """ return whether the target affects splicing """
        expt = False
        if action:
            action = '_'+action

        # unify this with SpliceSite
        if isinstance(self.reg, RegSpanAnno): # span
            if hasattr(self.reg, 'splice_donors'):
                if len(self.reg.splice_donors) > 0:
                    self.csqn.append("SpliceDonor"+csqn_action)
                for exind, chrm, spos in self.reg.splice_donors:
                    expt = True
                    self.append_info(
                        'C2=donor_splice_site_on_exon_%d_at_%s:%d%s' % (exind, chrm, spos, action))

            if hasattr(self.reg, 'splice_acceptors'):
                if len(self.reg.splice_acceptors) > 0:
                    self.csqn.append("SpliceAcceptor"+csqn_action)
                for exind, chrm, spos in self.reg.splice_acceptors:
                    expt = True
                    self.append_info(
                        'C2=acceptor_splice_site_on_exon_%d_at_%s:%d%s' % (exind, chrm, spos, action))

            if hasattr(self.reg, 'splice_both') and self.reg.splice_both:
                expt = True
                self.append_info('whole_exon_[%s]%s' % (','.join(map(str,self.reg.splice_both)), action))

            if hasattr(self.reg, 'cross_start') and self.reg.cross_start:
                expt = True
                if self.reg.t.strand == '+':
                    self.csqn.append('CdsStart'+csqn_action)
                    self.append_info('cds_start_at_%s:%d%s' %
                                     (self.reg.t.chrm, self.reg.t.cds_beg, action))
                else:
                    self.csqn.append('CdsStop'+csqn_action)
                    self.append_info('cds_stop_at_%s:%d%s' %
                                     (self.reg.t.chrm, self.reg.t.cds_beg, action))

            if hasattr(self.reg, 'cross_end') and self.reg.cross_end:
                expt = True
                if self.reg.t.strand == '+':
                    self.csqn.append('CdsStop'+csqn_action)
                    self.append_info('cds_end_at_%s:%d%s' %
                                     (self.reg.t.chrm, self.reg.t.cds_end, action))
                else:
                    self.csqn.append('CdsStart'+csqn_action)
                    self.append_info('cds_start_at_%s:%d%s' %
                                     (self.reg.t.chrm, self.reg.t.cds_end, action))
        else:                   # single site
            if hasattr(self.reg, 'splice'):
                if not self.reg.splice.nextto and csqn_action != "Synonymous": # hit splice site, not just next to it
                    expt = True
                    self.csqn.append("Splice"+self.reg.splice.stype+csqn_action)
                self.append_info('C2='+self.reg.splice.format())
            if self.reg.cds_beg is not None:
                if csqn_action != "Synonymous":
                    expt = True
                self.csqn.append("CdsStart"+csqn_action)
                self.append_info('C2=cds_start_at_%s:%d' % (self.reg.t.chrm, self.reg.cds_beg))
            if self.reg.cds_end is not None:
                if csqn_action != "Synonymous":
                    expt = True
                self.csqn.append("CdsStop"+csqn_action)
                self.append_info('C2=cds_end_at_%s:%d' % (self.reg.t.chrm, self.reg.cds_end))
            if hasattr(self.reg, 'tss'):
                if csqn_action != "Synonymous":
                    expt = True
                self.append_info('transcription_start_at_%s:%d' % (self.reg.t.chrm, self.reg.tss))
            if hasattr(self.reg, 'tes'):
                if csqn_action != "Synonymous":
                    expt = True
                self.append_info('transcription_end_at_%s:%d' % (self.reg.t.chrm, self.reg.tes))

        return expt

    def set_csqn_byreg(self, action=""):
        self.csqn.append(self.reg.csqn()+action)

    def gnuc(self):

        """ format in chr1:A12345T """
        s = self.chrm+':g.'
        if hasattr(self, 'gnuc_range') and self.gnuc_range: # gnuc_range always have priority of output
            s += self.gnuc_range
        else:
            if hasattr(self, 'gnuc_pos') and self.gnuc_pos: s += str(self.gnuc_pos)
            if hasattr(self, 'gnuc_ref') and self.gnuc_ref: s += self.gnuc_ref
            s += '>'
            if hasattr(self, 'gnuc_alt') and self.gnuc_alt: s += self.gnuc_alt
        if s == '.:g.>': return '.'
        return s

    def taa(self):
        """ format in HGVS nomenclature e.g., p.E545K """
        s = 'p.'
        if hasattr(self, 'taa_range') and self.taa_range:
            s += self.taa_range
        else:
            if hasattr(self, 'taa_ref') and self.taa_ref: s += self.taa_ref
            if hasattr(self, 'taa_pos') and self.taa_pos: s += str(self.taa_pos)
            if hasattr(self, 'taa_alt') and self.taa_alt: s += self.taa_alt
        if s == 'p.': return '.'
        return s

    def format_id(self):
        return '%s/%s/%s' % (self.gnuc(), self.tnuc(), self.taa())

    def format(self, op, args = None):
        """ This is where all the formatting actually happens """

        s = op+'\t' if op else ''
        s += self.formats(args)

        try:
            print(s)
        except IOError:
            sys.exit(1)

    def formats(self, args): # format string

        if self.is_var:
            if len(self.csqn) == 0:
                self.prepend_info("CSQN=Unclassified")
            elif len(set(self.csqn)) == 1:
                self.prepend_info("CSQN="+self.csqn[0])
            else:
                self.prepend_info("CSQN=Multi:"+','.join(self.csqn)) # TODO: test on this and remove this category eventually

        if hasattr(self.reg, 't'):
            if self.reg.t.gene_dbxref:
                self.append_info('dbxref=%s' % self.reg.t.gene_dbxref)
            if self.reg.t.aliases:
                self.append_info('aliases=%s' % ','.join(self.reg.t.aliases))
            if self.reg.t.source:
                self.append_info('source=%s' % self.reg.t.source)

        s = template.format(r=self, reg=self.reg.format(),
                gnuc=self.gnuc(), tnuc = self.tnuc(), taa = self.taa())

        if args is not None and args.gseq:

            long_msg = '[LONG SEQUENCE, see --seqmax]'
            s += '\t%s\t%s\t%s\t%s' % (self.chrm,
                str(self.vcf_pos) if hasattr(self, 'vcf_pos') and self.vcf_pos else '.',
                str(self.vcf_ref) if hasattr(self, 'vcf_ref') and self.vcf_ref else long_msg,
                str(self.vcf_alt) if hasattr(self, 'vcf_alt') and self.vcf_alt else long_msg)

        return s

def format_one(r, rs, qop, args):
    if not args.oneline:
        r.format(qop, args)
    else:
        rs.append(r.formats(args))

def format_records(records, qop, args, custom_match=False):

    """Print records
    This is the function all annotation will return.
    """
    fqop = ("*" + qop) if args.custom and not custom_match else qop
    if len(records) > 0:
        if args.oneline:
            s = fqop +'\t' if fqop else ''
            s += '\t|||\t'.join([r.formats(args) for r in records])
            try:
                print(s)
            except IOError:
                sys.exit(1)
        else:
            for r in records:
                r.format(fqop, args)
    else:
        r = Record()
        r.append_info('no_valid_transcript_found')
        r.format(fqop, args)

def wrap_exception(e, op, args):
    r = Record()
    r.append_info("Error="+str(e))

    if args.verbose > 1:
        err_warn(str(e))

    # r.format(op, args)
    if args.suspend:
        raise e
    return r




