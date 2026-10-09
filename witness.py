#!/usr/bin/env python3
"""Standalone, standard-library-only reader for Witness journal format 2.

Exported as witness.py into Witness.Repo by dings-gpt index migrate.
"""

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def _Object(Pairs):
	Result = {}
	for Key, Value in Pairs:
		if Key in Result:
			raise ValueError('Duplicate JSON key: ' + Key)
		Result[Key] = Value
	return Result


def _Invalid_Constant(Value):
	raise ValueError('Invalid JSON constant: ' + Value)


def _Read_Line(Line, Number):
	if not Line.endswith(b'\n'):
		raise ValueError('Incomplete JSONL line ' + str(Number))
	try:
		Row = json.loads(Line.decode('utf-8'), object_pairs_hook=_Object,
			parse_constant=_Invalid_Constant)
	except (ValueError, UnicodeError) as Error:
		raise ValueError('JSONL line ' + str(Number) + ': ' + str(Error)) from Error
	if not isinstance(Row, dict):
		raise ValueError('JSONL line ' + str(Number) + ' is not an Object')
	return Row


def Read_Lines(Path_Value):
	with Path(Path_Value).open('rb') as Stream:
		for Number, Line in enumerate(Stream, 1):
			yield _Read_Line(Line, Number)


def _Match(Value, Pattern, Label):
	if not isinstance(Value, str) or not re.fullmatch(Pattern, Value):
		raise ValueError('Invalid ' + Label)


def _Integer(Value, Label):
	if type(Value) is not int or Value < 0:
		raise ValueError('Invalid ' + Label)


def _Fingerprint(Value):
	_Match(Value, r'(?:sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})', 'Fingerprint')


def _Validate_Version(Row):
	if 'Version' in Row:
		_Match(Row['Version'], re.escape(Row['Number']) + r'\.V\.(0|[1-9][0-9]*)', 'Version')
		_Fingerprint(Row.get('Version_Fingerprint'))
	Files = Row.get('Files', [])
	if not isinstance(Files, list) or (Files and 'Version' not in Row):
		raise ValueError('Files require an exact Version')
	Selectors = set()
	for File in Files:
		if not isinstance(File, dict):
			raise ValueError('Invalid File')
		_Match(File.get('Selector'), r'[A-Za-z0-9][A-Za-z0-9._-]*', 'Selector')
		if File['Selector'] in Selectors:
			raise ValueError('Duplicate File Selector')
		Selectors.add(File['Selector'])
		_Integer(File.get('Byte_Size'), 'Byte_Size')
		Hashes = File.get('Hash_List')
		if not isinstance(Hashes, list) or not Hashes:
			raise ValueError('File requires hashes')
		for Hash in Hashes:
			Pattern = {'SHA-1': r'sha1:[0-9a-f]{40}', 'SHA-256': r'sha256:[0-9a-f]{64}'}
			if not isinstance(Hash, dict) or Hash.get('Algorithm') not in Pattern:
				raise ValueError('Unsupported Hash Algorithm')
			_Match(Hash.get('Digest'), Pattern[Hash['Algorithm']], 'Digest')


def _Validate_Metadata(Metadata):
	if Metadata.get('Type') != 'Witness_Index' or type(Metadata.get('Format_Version')) is not int or Metadata['Format_Version'] != 2:
		raise ValueError('Expected Witness_Index journal format 2 header')
	if Metadata.get('State') != 'Migration_Candidate':
		raise ValueError('Unsupported Witness State')
	for Key in ['Source_Commit', 'World_Git_Commit', 'Access_Git_Commit']:
		_Match(Metadata.get(Key), r'(?:[0-9a-f]{40}|[0-9a-f]{64})', Key)
	for Key in ['Source_SHA256', 'History_SHA256']:
		_Match(Metadata.get(Key), r'[0-9a-f]{64}', Key)
	for Key in ['Initial_Reservation_Count', 'History_Count']:
		_Integer(Metadata.get(Key), Key)
	if 'Versions_SHA256' in Metadata or 'Version_Count' in Metadata:
		_Match(Metadata.get('Versions_SHA256'), r'[0-9a-f]{64}', 'Versions_SHA256')
		_Integer(Metadata.get('Version_Count'), 'Version_Count')
	_Match(Metadata.get('World'), r'W\.V\.(0|[1-9][0-9]*)', 'World')
	_Fingerprint(Metadata.get('World_Fingerprint'))


def _Validate_Number(Number):
	_Match(Number, r'0|[1-9][0-9]*', 'Number')
	if int(Number) > 2**63 - 1:
		raise ValueError('Dings Number exceeds signed-64-bit storage')


def _Validate_Reservation(Row):
	if Row.get('Type') != 'Reservation':
		raise ValueError('Expected Reservation')
	_Validate_Number(Row.get('Number'))
	if type(Row.get('In_Current_Index')) is not bool:
		raise ValueError('In_Current_Index must be Bool')
	if 'First_Index_Commit' in Row:
		_Match(Row['First_Index_Commit'], r'(?:[0-9a-f]{40}|[0-9a-f]{64})', 'First_Index_Commit')
	if 'Name' in Row:
		if not isinstance(Row['Name'], str) or not Row['Name'].strip() or any(C in Row['Name'] for C in '\r\n\t') or Row.get('Name_Source') not in ['Legacy_Index', 'Registration']:
			raise ValueError('Invalid Index Name')
	_Validate_Version(Row)
	if 'Legacy_Hash_Assertion' in Row:
		Hash = Row['Legacy_Hash_Assertion']
		Pattern = {'SHA-1': r'[0-9a-f]{40}', 'SHA-256': r'[0-9a-f]{64}'}
		if not isinstance(Hash, dict) or Hash.get('Algorithm') not in Pattern:
			raise ValueError('Invalid Legacy_Hash_Assertion')
		_Match(Hash.get('Digest'), Pattern[Hash['Algorithm']], 'Legacy Digest')


def _Validate_Version_Record(Row):
	if Row.get('Type') != 'Dings_Version' or 'Version' not in Row:
		raise ValueError('Expected Dings_Version with exact Version Address')
	_Validate_Number(Row.get('Number'))
	_Validate_Version(Row)
	# Version events never replace reservation Names or allocation metadata.
	if set(Row) - {'Type', 'Number', 'Version', 'Version_Fingerprint', 'Files',
		'World', 'World_Fingerprint', 'World_BCT', 'Witness_BCT'}:
		raise ValueError('Unsupported Dings_Version field')
	if 'World' in Row:
		_Match(Row['World'], r'W\.V\.(0|[1-9][0-9]*)', 'World')
		_Fingerprint(Row.get('World_Fingerprint'))


def _Validate_World_Record(Row):
	if Row.get('Type') != 'World_Witness' or set(Row) != {'Type', 'World', 'World_Fingerprint', 'World_BCT', 'Version_Count'}:
		raise ValueError('Invalid World_Witness record')
	_Match(Row['World'], r'W\.V\.(0|[1-9][0-9]*)', 'World')
	_Fingerprint(Row['World_Fingerprint'])
	_Integer(Row['Version_Count'], 'Version_Count')
	if not isinstance(Row['World_BCT'], str) or not Row['World_BCT'].startswith('BCT+'):
		raise ValueError('Invalid World BCT')


class Journal_View:
	"""Replay immutable seed records and appended records into an in-memory view."""
	def __init__(Self, Metadata, Keep_Files=True):
		_Validate_Metadata(Metadata)
		Self.Metadata = dict(Metadata)
		Self.Keep_Files = Keep_Files
		Self.Seed_Rows = []
		Self.By_Number = {}
		Self.Appended_Versions = {}
		Self.Maximum_Number = -1
		Self.Last_World = None
		Self.World_Version_Count = 0

	def _Stored(Self, Row):
		return Row if Self.Keep_Files else {K: Row[K] for K in ['Number', 'Name', 'Version'] if K in Row}

	def Apply(Self, Row):
		Seed = len(Self.Seed_Rows) < Self.Metadata['Initial_Reservation_Count']
		if not Seed and Row.get('Type') == 'World_Witness':
			_Validate_World_Record(Row)
			Previous = Self.Last_World or Self.Metadata
			if int(Row['World'][4:]) != int(Previous['World'][4:]) + 1:
				raise ValueError('Witness Worlds must be consecutive')
			if Row['Version_Count'] != Self.World_Version_Count:
				raise ValueError('World_Witness Version_Count differs')
			Self.Last_World = dict(Row)
			Self.World_Version_Count = 0
			return
		if Seed or Row.get('Type') == 'Reservation':
			_Validate_Reservation(Row)
			Number = Row['Number']
			if Number in Self.By_Number:
				raise ValueError('Reservations must be unique')
			if Seed and int(Number) <= Self.Maximum_Number:
				raise ValueError('Initial reservations must be numerically ordered')
			if not Seed and ('Version' in Row or 'First_Index_Commit' in Row or 'Legacy_Hash_Assertion' in Row):
				raise ValueError('New reservations cannot contain migration or Version evidence')
			Stored = Self._Stored(Row)
			Self.By_Number[Number] = Stored
			Self.Maximum_Number = max(Self.Maximum_Number, int(Number))
			if Seed:
				Self.Seed_Rows.append(Stored)
			return
		_Validate_Version_Record(Row)
		if Row['Number'] not in Self.By_Number:
			raise ValueError('Version requires a reserved Number')
		if Row['Version'] in Self.Appended_Versions:
			raise ValueError('Duplicate Version Address in journal')
		Self.Appended_Versions[Row['Version']] = Self._Stored(Row)
		Self.World_Version_Count += 1
		Current = Self.By_Number[Row['Number']]
		if 'Version' not in Current or int(Row['Version'].split('.V.')[1]) > int(Current['Version'].split('.V.')[1]):
			Base = {K: V for K, V in Current.items() if K not in ['Version', 'Version_Fingerprint', 'Files', 'World', 'World_Fingerprint', 'World_BCT', 'Witness_BCT']}
			Self.By_Number[Row['Number']] = Self._Stored(dict(Base, **{K: V for K, V in Row.items() if K not in ['Type', 'Number']}))

	def Complete(Self):
		if len(Self.Seed_Rows) != Self.Metadata['Initial_Reservation_Count']:
			raise ValueError('Initial_Reservation_Count differs')

	def Result(Self):
		Self.Complete()
		return dict(Self.Metadata, Reservation_Count=len(Self.By_Number)), sorted(Self.By_Number.values(), key=lambda R: int(R['Number']))


class Journal_Index:
	"""A disposable memory index; Refresh consumes only the appended tail."""
	def __init__(Self, Path_Value):
		Self.Path = Path(Path_Value)
		Self.View = None
		Self.Signature = None
		Self.Offset = 0
		Self.Line_Count = 0

	def Refresh(Self):
		Stat = Self.Path.stat()
		Signature = (Stat.st_dev, Stat.st_ino, Stat.st_size, Stat.st_mtime_ns, Stat.st_ctime_ns)
		if Signature == Self.Signature:
			return Self
		Append = Self.View is not None and Signature[:2] == Self.Signature[:2] and Stat.st_size > Self.Offset
		try:
			with Self.Path.open('rb') as Stream:
				if Append:
					Stream.seek(Self.Offset)
				else:
					Self.View = Journal_View(_Read_Line(Stream.readline(), 1))
					Self.Line_Count = 1
				for Line in Stream:
					Self.Line_Count += 1
					Self.View.Apply(_Read_Line(Line, Self.Line_Count))
				Self.View.Complete()
				Self.Offset = Stream.tell()
			Self.Signature = Signature
		except Exception:
			Self.View = None
			Self.Signature = None
			Self.Offset = 0
			raise
		return Self


def Read_Index(Path_Value):
	return Journal_Index(Path_Value).Refresh().View.Result()


def Validate_Index(Rows):
	Lines = iter(Rows)
	View = Journal_View(next(Lines, {}))
	for Row in Lines:
		View.Apply(Row)
	return View.Result()


def Check(Path_Value):
	Index = Journal_Index(Path_Value).Refresh()
	Metadata, Rows = Index.View.Result()
	History = Path(Path_Value).parent / 'Index-History.jsonl'
	Validate_History(Metadata, Rows, list(Read_Lines(History)), History.read_bytes())
	if 'Versions_SHA256' in Metadata or Index.View.Appended_Versions:
		_Versions(Index)
	return Metadata, Rows


def _Versions(Index):
	View = Index.View
	Metadata = View.Metadata
	if 'Versions_SHA256' in Metadata:
		Path_Value = Index.Path.parent / 'Dings-Versions.jsonl'
		Versions = list(Read_Lines(Path_Value))
		Validate_Versions(Metadata, View.Seed_Rows, Versions, Path_Value.read_bytes())
	else:
		Versions = []
		if any('Version' in Row for Row in View.Seed_Rows):
			raise ValueError('This Witness Index has no historical Versions export')
	By_Address = {V['Version']: V for V in Versions}
	for Address, Version in View.Appended_Versions.items():
		if Address in By_Address:
			raise ValueError('Duplicate Version Address in seed and journal: ' + Address)
		By_Address[Address] = Version
	return sorted(By_Address.values(), key=lambda V: (int(V['Number']), int(V['Version'].split('.V.')[1])))


def Read_Versions(Path_Value, Metadata, Rows):
	return _Versions(Journal_Index(Path_Value).Refresh())


def Validate_Versions(Metadata, Rows, Versions, Payload):
	_Match(Metadata.get('Versions_SHA256'), r'[0-9a-f]{64}', 'Versions_SHA256')
	_Integer(Metadata.get('Version_Count'), 'Version_Count')
	if hashlib.sha256(Payload).hexdigest() != Metadata['Versions_SHA256']:
		raise ValueError('Dings-Versions.jsonl SHA256 differs')
	if len(Versions) != Metadata['Version_Count']:
		raise ValueError('Version_Count differs')
	Reservations = {Row['Number']: Row for Row in Rows}
	By_Address, Previous = {}, (-1, -1)
	for Version in Versions:
		if Version.get('Type') != 'Dings_Version' or Version.get('Number') not in Reservations:
			raise ValueError('Version requires a reserved Number')
		if 'Version' not in Version:
			raise ValueError('Missing exact Version Address')
		_Validate_Version(Version)
		Order = (int(Version['Number']), int(Version['Version'].split('.V.')[1]))
		if Order <= Previous:
			raise ValueError('Versions must be unique and numerically ordered')
		Previous = Order
		By_Address[Version['Version']] = Version
	for Row in Rows:
		if 'Version' in Row:
			Version = By_Address.get(Row['Version'], {})
			if any(Version.get(Key) != Row.get(Key) for Key in
				['Version_Fingerprint', 'Files', 'World', 'World_Fingerprint', 'World_BCT', 'Witness_BCT']):
				raise ValueError('Current Version differs from historical Versions export: ' + Row['Version'])


def Validate_History(Metadata, Rows, Proofs, Payload):
	if hashlib.sha256(Payload).hexdigest() != Metadata['History_SHA256']:
		raise ValueError('Index-History.jsonl SHA256 differs')
	Commits = set()
	for Proof in Proofs:
		if Proof.get('Type') != 'Index_Source':
			raise ValueError('Invalid Index history record')
		_Match(Proof.get('Commit'), r'(?:[0-9a-f]{40}|[0-9a-f]{64})', 'Commit')
		if Proof['Commit'] in Commits:
			raise ValueError('Duplicate history Commit')
		Commits.add(Proof['Commit'])
		_Integer(Proof.get('Commit_Time_Unix'), 'Commit_Time_Unix')
		if Proof.get('Absent') is not True:
			_Match(Proof.get('SHA256'), r'[0-9a-f]{64}', 'History SHA256')
			_Integer(Proof.get('Number_Count'), 'Number_Count')
			_Integer(Proof.get('Parse_Error_Count'), 'Parse_Error_Count')
		if not isinstance(Proof.get('World_List'), list):
			raise ValueError('Invalid historical World associations')
		for World in Proof['World_List']:
			_Match(World.get('World'), r'W\.V\.(0|[1-9][0-9]*)', 'World')
			_Fingerprint(World.get('Version_Fingerprint'))
	if len(Proofs) != Metadata['History_Count']:
		raise ValueError('History_Count differs')
	if any(Row.get('First_Index_Commit') not in Commits for Row in Rows if 'First_Index_Commit' in Row):
		raise ValueError('Reservation refers to missing historical evidence')


class Help_Formatter(argparse.RawDescriptionHelpFormatter):
	def _format_usage(self, usage, actions, groups, prefix):
		return super()._format_usage(usage, actions, groups, prefix or 'Usage: ')


def Main(Arguments=None):
	Parser = argparse.ArgumentParser(add_help=False, formatter_class=Help_Formatter,
		description='''Read Witness JSONL without an All-Dings Installation.

Sub-Commands:
  list      Show an aligned Table of reserved Dings Numbers, exact Versions,
            registration Names, Files and recorded SHA1 Hashes.
            -verbose also shows SHA256 Hashes.
  show      Show the latest recorded Version of one Dings Number, or an exact
            historical Version Address such as 400007578.V.0.
  check     Validate the Index Structure and linked History Hash.
            Does not verify original File Contents or prove Possession.
  markdown  Generate a Markdown View ordered by Dings Number.''',
		epilog='''Examples:
  witness.py list
  witness.py list -verbose
  witness.py list '*Parking*'
  witness.py show 400007578
  witness.py show 400007578.V.0
  witness.py check
  witness.py markdown > Dings_World_Index.md
  witness.py --index /path/to/World-Index.jsonl list

Names record registration or the legacy Index. Hashes come from recorded World Evidence;
the Reader does not recompute them from original Files.''')
	Optional = Parser.add_argument_group('Optional Arguments')
	Optional.add_argument('-h', '--help', action='help', help='Show this Help-Message and exit')
	Optional.add_argument('-verbose', '--verbose', action='store_true',
		help='Show SHA1 and SHA256 Hashes for list; Default: SHA1 only')
	Optional.add_argument('--index', type=Path, default=Path(__file__).with_name('World-Index.jsonl'),
		metavar='INDEX', help='Index JSONL File; Default: World-Index.jsonl beside witness.py')
	Positional = Parser.add_argument_group('Arguments')
	Positional.add_argument('command', choices=['list', 'show', 'check', 'markdown'],
		help='Select the Sub-Command')
	Positional.add_argument('selector', nargs='?', default='*', metavar='Selector',
		help='Number or Name Glob for list/markdown (Default: *); Number or NUMBER.V.VERSION for show')
	Options = Parser.parse_args(Arguments)
	try:
		Metadata, Rows = Check(Options.index) if Options.command == 'check' else Read_Index(Options.index)
		if Options.command == 'check':
			print('Valid format and linked history: ' + str(len(Rows)) + ' reservations; ' + Metadata['State'])
			print('This checks recorded structure and history hashes, not original file bytes or allocation readiness.')
			return 0
		if Options.command == 'show':
			Address = re.fullmatch(r'(0|[1-9][0-9]*)\.V\.(0|[1-9][0-9]*)', Options.selector)
			Number = Address.group(1) if Address else Options.selector
			Selected = [Row for Row in Rows if Row['Number'] == Number]
			if not Selected:
				raise ValueError('Number is not reserved: ' + Number)
			if Address and Selected[0].get('Version') != Options.selector:
				Versions = Read_Versions(Options.index, Metadata, Rows)
				Version = next((V for V in Versions if V['Version'] == Options.selector), None)
				if Version is None:
					raise ValueError('Version is not recorded in this Witness Index: ' + Options.selector)
				Selected = [dict(Selected[0], **{K: Version[K] for K in ['Version', 'Version_Fingerprint', 'Files']})]
			Rows = Selected
		else:
			Rows = [Row for Row in Rows if fnmatch.fnmatchcase(Row['Number'], Options.selector)
				or fnmatch.fnmatchcase(Row.get('Name', ''), Options.selector)]
		if Options.command == 'markdown':
			print('# Dings World Index\n')
			print('Initial Migration World: ' + Metadata['World'] + '. Latest recorded Versions are shown.\n')
			print('State: ' + Metadata['State'] + '. Names record registration or the legacy Index.\n')
			for Row in sorted(Rows, key=lambda R: int(R['Number'])):
				print('* ' + Row.get('Version', Row['Number']) + ' ' + Row.get('Name', '(unnamed)'))
			return 0
		Table = [('Version / Number', 'Index Name', 'File', 'Hashes')]
		All_Hashes = Options.command != 'list' or Options.verbose
		for Row in Rows:
			Files = Row.get('Files') or [None]
			for File in Files:
				Hashes = ', '.join(H['Digest'] for H in File['Hash_List']
					if All_Hashes or H['Digest'].startswith('sha1:')) if File else ''
				if not File and 'Legacy_Hash_Assertion' in Row:
					Assertion = Row['Legacy_Hash_Assertion']
					if All_Hashes or Assertion['Algorithm'] == 'SHA-1':
						Hashes = 'Unverified legacy assertion: ' + Assertion['Digest']
				Name = Row['Number'] + '.' + File['Selector'] if File else '-'
				Table.append((Row.get('Version', Row['Number']), Row.get('Name', '-'), Name, Hashes))
		Widths = [max(len(Row[Index]) for Row in Table) for Index in range(len(Table[0]) - 1)]
		for Row in Table:
			print('  '.join(Value.ljust(Width) for Value, Width in zip(Row, Widths)) + '  ' + Row[-1])
		return 0
	except BrokenPipeError:
		raise
	except (OSError, ValueError, TypeError, KeyError) as Error:
		print('Witness Error: ' + str(Error), file=sys.stderr)
		return 1


if __name__ == '__main__':
	try:
		Exit_Status = Main()
		sys.stdout.flush()
	except BrokenPipeError:
		# A consumer such as head has finished. Prevent another failure at shutdown.
		with open(os.devnull, 'w') as Sink:
			os.dup2(Sink.fileno(), sys.stdout.fileno())
		Exit_Status = 0
	sys.exit(Exit_Status)
