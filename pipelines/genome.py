#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path as op
import sys
import time
import logging

from maize.apps.base import eprint, sh, mkdir
from maize.formats.base import must_open
from maize.formats.pbs import PbsJob

def check_genomedir(species, raw = False):
    dirw = species
    if species.isalnum():
        dirw = op.join("/home/springer/zhoux379/data/genome", species)
        logging.debug("converting species to directory: %s" % dirw)
    if not op.isdir(dirw):
        logging.debug("creating diretory: %s" % dirw)
        mkdir(dirw)
    if raw:
        fis = ['raw.fas', 'raw.fa', 'raw.fas.gz', 'raw.fa.gz']
        fis = [x for x in fis if op.isfile(op.join(dirw, x))]
        if len(fis) == 0:
            logging.error("no raw.fas found")
            sys.exit()
        elif len(fis) > 1:
            logging.error(">1 raw.fas found")
            sys.exit()
        return dirw, fis[0]
    else:
        fg = "%s/11_genome.fas" % dirw
        if not op.isfile(fg):
            logging.error("%s not there" % fg)
            sys.exit()
        return op.abspath(dirw), op.abspath(fg)

def clean_fasta(args):
    dirw, fi = check_genomedir(args.species, raw = False)
    os.chdir(dirw)
    for fname in ["raw.fix.fas.index", "11_genome.fas.index"]:
        if op.isfile(fname):
            os.remove(fname)
    if op.islink("11_genome.fas"): os.unlink("11_genome.fas")
   
    if op.isfile("11_genome.fas") and not args.overwrite:
        logging.debug("11_genome.fas already exits: skipped")
    else:
        sh("fasta clean %s > 01.fas" % fi)

        if args.rename:
            sh("fasta rename --map 03.seqid.map 01.fas > 11_genome.fas")
            os.remove("01.fas")
        else:
            sh("mv 01.fas 11_genome.fas")
    
    if op.isfile("ctg.raw.fas"):
        sh("fasta clean ctg.raw.fas > ctg.fas")

    if op.isfile("15.sizes") and not args.overwrite:
        logging.debug("15.sizes already exits - skipped")
    else:
        sh("fasta size 11_genome.fas > 15.sizes")
    
    if op.isfile("15.bed") and not args.overwrite:
        logging.debug("15.bed already exits - skipped")
    else:
        sh("fasta size --bed 11_genome.fas > 15.bed")
    
    if op.isfile("16.gap.bed") and not args.overwrite:
        logging.debug("16.gap.bed already exits - skipped")
    else:
        sh("fasta gaps 11_genome.fas > 16.gap.bed")

def build_blat(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.blat")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
   
    if not args.overwrite and op.isfile('db.2bit'):
        logging.debug("db.2bit already exists - skipped")
    else:
        sh("faToTwoBit %s db.2bit" % fg)
        sh("blat db.2bit tmp.fas tmp.out -makeOoc=db.2bit.tile11.ooc")
    if op.isfile("tmp.out"): os.remove("tmp.out")

def build_bowtie(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.bowtie2")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
    
    if op.isfile("db.rev.1.bt2") and not args.overwrite:
        logging.debug("db.*.bt2 already exists - skipped")
    else:
        sh("rm -rf *")
        sh("ln -sf %s db.fa" % fg)
        # need to "module load bowtie2"
        sh("bowtie2-build db.fa db")

def build_hisat(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.hisat2")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
   
    if op.isfile("db.1.ht2") and not args.overwrite:
        logging.debug("db.1.ht2 already exists - skipped")
    elif not op.isfile("../51.gtf"):
        logging.error("no gtf file: ../51.gtf")
        sys.exit()
    else:
        sh("hisat2_extract_exons.py ../51.gtf > db.exon")
        sh("hisat2_extract_splice_sites.py ../51.gtf > db.ss")
        sh("hisat2-build -p %d --ss db.ss --exon db.exon %s db" % (args.p, fg))

def build_star(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.star")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
   
    if op.isfile("SA") and not args.overwrite:
        logging.debug("SA already exists - skipped")
    elif not op.isfile("../51.gtf"):
        logging.error("no gtf file: ../51.gtf")
        sys.exit()
    else:
        sh("STAR --runThreadN %d --runMode genomeGenerate --genomeDir %s \
                --genomeFastaFiles %s --sjdbGTFfile %s" %
                (args.p, ".", fg, "../51.gtf"))

def build_bwa(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.bwa")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
   
    if op.isfile("db.bwt") and not args.overwrite:
        logging.debug("db.bwt already exists - skipped")
    else:
        sh("bwa index -a bwtsw -p %s/db %s" % (dirw, fg))

def build_gatk(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "21.gatk")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)
   
    if op.isfile("db.dict") and not args.overwrite:
        logging.debug("db.dict already exists - skipped")
    else:
        if op.exists("db.fasta"): sh("rm db.fasta")
        if op.exists("db.dict"): sh("rm db.dict")
        sh("cp ../11_genome.fas db.fasta")
        sh("gatk CreateSequenceDictionary -R db.fasta")
        sh("samtools faidx db.fasta")

def repeatmasker(args):
    dirg, fg = check_genomedir(args.species)
    dirw = op.join(dirg, "12.repeatmasker")
    if not op.isdir(dirw): os.makedirs(dirw)
    os.chdir(dirw)

    species = None
    if args.species in ['Zmays', 'B73', 'PH207', 'W22', 'Mo17', 'PHB47']:
        species = 'maize'
    elif args.species == 'Osativa':
        species = 'rice'
    else:
        logging.error("%s not supported" % args.species)
        sys.exit(1)
    
    cmds = []
    cmds.append("cd %s" % dirw)
    cmds.append("RepeatMasker -pa %d -species %s -dir %s %s" % (args.p, species, dirw, fg)),
    cmds.append("parse.rm.pl -i 11_genome.fas.out -o 12.repeatmasker.tsv")
    
    pbsjob = PbsJob(queue = 'ram256g', ppn = 24, walltime = "10:00:00", cmds = "\n".join(cmds))
    fjob = op.join(dirg, "13.rm.pbs")
    pbsjob.write(fjob)
    logging.debug("Job script '%s' has been created" % fjob)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
            description = 'process genome files and build genome DB'
    )
    sp = parser.add_subparsers(title = 'available commands', dest = 'command')

    sp1 = sp.add_parser("fasta", 
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
            help = "clean and rename fasta records, generate *.sizes and gap location files")
    sp1.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp1.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp1.add_argument('--rename', action = 'store_true', help = 'rename seq IDs')
    sp1.set_defaults(func = clean_fasta)

    sp1 = sp.add_parser("repeatmasker", 
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
            help = "run repeatmasker and parse result"
    )
    sp1.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp1.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp1.add_argument('--p', type = int, default = 24, help = 'number of threads')
    sp1.set_defaults(func = repeatmasker)

    sp2 = sp.add_parser("blat", help = "build Blat DB")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.set_defaults(func = build_blat)
    
    sp2 = sp.add_parser("bowtie", help = "build Bowtie2 DB")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.set_defaults(func = build_bowtie)
    
    sp2 = sp.add_parser("bwa", help = "build bwa DB")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.set_defaults(func = build_bwa)
    
    sp2 = sp.add_parser("hisat", help = "build hisat2 DB")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.add_argument('--p', type = int, default = 24, help = 'number of threads')
    sp2.set_defaults(func = build_hisat)
    
    sp2 = sp.add_parser("star", help = "build STAR DB")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.add_argument('--p', type = int, default = 24, help = 'number of threads')
    sp2.set_defaults(func = build_star)
    
    sp2 = sp.add_parser("gatk", help = "build GATK ref-db")
    sp2.add_argument('species', help = 'species/accession/genotype/dir-path')
    sp2.add_argument('--overwrite', action='store_true', help = 'overwrite')
    sp2.set_defaults(func = build_gatk)
    
    args = parser.parse_args()
    if args.command:
        args.func(args)
    else:
        print('Error: need to specify a sub command\n')
        parser.print_help()
