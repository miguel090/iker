#!/usr/bin/env python3
'''
iker.py script courtesy of Portcullis Security

https://labs.portcullis.co.uk/tools/iker/

Modifications from original v1.1 script:
	Added shebang for python binary above
	
'''
###############################################################################
### iker.py
### 
### This tool can be used to analyse the security of a IPsec based VPN.
### 
### This script is under GPL v3 License:
### 
###                                http://www.gnu.org/licenses/gpl-3.0.html
### 
### From a IP address/range or a list of them, iker.py uses ike-scan to 
### look for common misconfiguration in VPN concentrators.
### 
### In this version, iker does:
### 
### * VPNs discovering
### * check for IKE v2 support
### * vendor IDs (VID) extraction
### * implementation guessing (backoff)
### * list supported transforms in Main Mode
### * check aggressive mode and list supported transforms in this mode
### * enumerate valid client/group IDs in aggressive mode
### * analyse results to extract actual issues
### * support 2 output formats
### 
### FIXED BUGS / NEW FEATURES:
### 
### * Identify if ike-scan launches any error during the scan
### * Improved the GUI by adding a progressbar and the current transform
### * Skip feature
### * Capability to exit at any time saving results
### * Fixed a bug that did not identify IKE v2 when IKE v1 was not supported
###
### Modifications from v1.2 script, by Zamanry https://github.com/Zamanry/iker
### 	Added all known algorithms
### 	Added Python2+ and Python3+ support
### 	Updated flaws with industry standards
### 	Removed flaws stating static risk as risk is dynamic
### 	Fixed grammar and updated technical terms (key exchange over Diffie-Hellman)
### 
### v1.3 
### Combined commit from https://github.com/Zamanry/iker/pull/26/commits/cdbfcd62c71dbb79b84aa277acb3274a9099eccb
### * Scan IKEv2
###
### v1.4 FIXED BUGS:
### 
### * Fixed bug not allowing the scan to occurr correctly, by changing the approach to always transform the output of commands to strings and not mix bytes (different from Zamanry implementation)
### * Fixed typo of proccess
### * Fixed issue with inconsistent IKEv2 information
### * Fix incomplete IKEv2 implementation, and added arguments to specify its protocols
### 
### How to use it? That's easy!
###
### # python iker.py -i ips.txt -o iker_output.txt -x iker_output.xml -v
### 
### Use -h option to complete help.
### 
### Original Author: Julio Gomez Ortega (JGO@portcullis-security.com)
### v1.2: Miguel Silva
### 
###############################################################################

from sys import exit, stdout
from os import geteuid
import subprocess
import argparse
from re import sub
from time import localtime, strftime, sleep

###############################################################################

# iker version
VERSION = "1.4"

# ike-scan full path
FULLIKESCANPATH = "ike-scan"

# Verbose flag (default False)
VERBOSE = False

# Encryption algorithms: DES, Triple-DES, AES/128, AES/192 and AES/256
ENCLIST = []
ENCLISTv2 = []

# Hash algorithms: MD5 and SHA1
HASHLIST = []
HASHLISTv2 = []

# Authentication methods: Pre-Shared Key, RSA Signatures, Hybrid Mode and XAUTH
AUTHLIST = []

# Diffie-Hellman groups: 1, 2 and 5
GROUPLIST = []

FULLENCLIST = ['1', '2', '3', '4', '5', '6', '7/128', '7/192', '7/256', '8', '65001', '65002', '65004', '65005']
FULLENCLISTv2 = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '12', '13', '14', '15,' '16', '18', '19', '20', '23']
FULLHASHLIST = ['1', '2', '3', '4', '5', '6']
FULLHASHLISTv2 = ['1', '2', '3', '4', '5', '6', '7', '8']
FULLAUTHLIST = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '128', '64221', '64223', '65001', '65003', '65005', '65007', '65009']
FULLGROUPLIST = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30']


# XML Output
XMLOUTPUT = "output.xml"

# Client IDs dictionary
CLIENTIDS = ""

# Delay between requests
DELAY = 0

# Flaws:
FLAW_DISC = "The IKE service could be discovered which should be restricted to only necessary parties"
FLAW_IKEV1 = "The following weak IKE version was supported: version 1"
FLAW_FING_VID = "The IKE service could be fingerprinted by analyzing the vendor ID (VID) which returned"
FLAW_FING_BACKOFF = "The IKE service could be fingerprinted by analyzing the responses received"
FLAW_ENC_DES = "The following weak encryption algorithm was supported: DES"
FLAW_ENC_IDEA = "The following weak encryption algorithm was supported: IDEA"
FLAW_ENC_BLOW = "The following weak encryption algorithm was supported: Blowfish"
FLAW_ENC_RC5 = "The following weak encryption algorithm was supported: RC5"
FLAW_ENC_CAST = "The following weak encryption algorithm was supported: CAST"
FLAW_ENC_3DES = "The following weak encryption algorithm was supported: 3DES"
FLAW_HASH_MD5 = "The following weak hash algorithm was supported: MD5"
FLAW_HASH_SHA1 = "The following weak hash algorithm was supported: SHA-1"
FLAW_DHG_1 = "The following weak key exchange group was supported: Diffie-Hellman group 1 (MODP-768)"
FLAW_DHG_2 = "The following weak key exchange group supported: Diffie-Hellman group 2 (MODP-1024)"
FLAW_DHG_5 = "The following weak key exchange group was supported: Diffie-Hellman group 5 (MODP-1536)"
FLAW_AUTH_PSK = "The following weak authentication method was supported: PSK"
FLAW_AUTH_DSA_SIG = "The following weak authentication method was supported: DSA signatures"
FLAW_AUTH_RSA_SIG = "The following moderate authentication method was supported: RSA signatures"
FLAW_AUTH_RSA_ENC = "The following weak authentication method was supported: RSA encryption"
FLAW_AUTH_RSA_ENC_REV = "The following moderate authentication method was supported: RSA revised encryption"
FLAW_AUTH_ELG_ENC = "The following weak authentication method was supported: ElGamel encryption"
FLAW_AUTH_ELG_ENC_REV = "The following weak authentication method was supported: ElGamel revised encryption"
FLAW_AUTH_ECDSA_SIG = "The following moderate authentication method was supported: ECDSA signature"
FLAW_AUTH_ECDSA_SHA256 = "The following moderate authentication method was supported: ECDSA SHA-256"
FLAW_AUTH_ECDSA_SHA384 = "The following moderate authenti`cation method was supported: ECDSA SHA-384"
FLAW_AUTH_ECDSA_SHA512 = "The following moderate authentication method was supported: ECDSA SHA-512"
FLAW_AUTH_CRACK = "The following weak authentication method was supported: ISPRA CRACK"
FLAW_AUTH_HYB_RSA = "The following weak authentication method was supported: Hybrid RSA signatures"
FLAW_AUTH_HYB_DSA = "The following weak authentication method was supported: Hybrid DSA signatures"
FLAW_AGGR = "Aggressive Mode was accepted by the IKE service which should be disabled"
FLAW_AGGR_GRP_NO_ENC = "Aggressive Mode transmits group name without encryption"
FLAW_CID_ENUM = "Client IDs could be enumerated which should be restricted to only necessary parties or disabled"



###############################################################################
### Methods
###############################################################################

###############################################################################
def welcome():
	'''This method prints a welcome message.'''
	
	print('''
iker v. %s

The ike-scan based script that checks for security flaws in IPsec-based VPNs.

                               by Julio Gomez ( jgo@portcullis-security.com )
''' % VERSION)
	

###############################################################################
def checkPrivileges():
	'''This method checks if the script was launched with root privileges.
	@return True if it was launched with root privs and False in other case.'''
	
	return geteuid() == 0

###############################################################################
def getArguments():
	'''This method parse the command line.
	@return the arguments received and a list of targets.'''
	global VERBOSE
	global FULLIKESCANPATH
	global ENCLIST
	global ENCLISTv2
	global HASHLIST
	global HASHLISTv2
	global AUTHLIST
	global GROUPLIST
	global XMLOUTPUT
	global CLIENTIDS
	global DELAY

	targets = []

	parser = argparse.ArgumentParser()

	parser.add_argument("target", type=str, nargs='?', help="The IP address or the network (CIDR notation) to scan.")

	parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose.")
	parser.add_argument("-d", "--delay", type=int, help="Delay between requests (in milliseconds). Default: 0 (No delay).")
	parser.add_argument("-i", "--input", type=str, help="An input file with an IP address/network per line.")
	parser.add_argument("-o", "--output", type=str, help="An output file to store the results.")
	parser.add_argument("-x", "--xml", type=str, help="An output file to store the results in XML format. Default: output.xml")
	parser.add_argument("--encalgs", type=str, default="1 5 7", help="The encryption algorithms to check (1-7). Default: DES(1), 3DES(5), AES(7). Example: --encalgs=\"1 2 3 4 5 6 7/128 7/192 7/256 8\"")
	parser.add_argument("--encalgsv2", type=str, default="1 5 7", help="The encryption algorithms to check in IKEv2 (1-7). Default: DES(1), 3DES(5), AES(7). Example: --encalgs=\"1 2 3 4 5 6 7/128 7/192 7/256 8\"")
	parser.add_argument("--hashalgs", type=str, default="1 2", help="The hash algorithms to check. Default: MD5(1) and SHA1(2). Example: --hashalgs=\"1 2 3 4 5 6\"")
	parser.add_argument("--hashalgsv2", type=str, default="1 2", help="The hash algorithms to check in IKEv2. Default: MD5(1) and SHA1(2). Example: --hashalgs=\"1 2 3 4 5 6\"")

	parser.add_argument("--authmethods", type=str, default="1 3 64221 65001", help="The authorization methods to check. Default: PSK(1), RSA Sig(3), Hybrid(64221), XAUTH(65001). Example: --authmethods=\"1 2 3 4 5 6 7 8 64221 65001\"")
	parser.add_argument("--kegroups", type=str, default="1 2 5 14", help="The key exchange groups to check. Default: MODP-768(1), MODP-1024(2), MODP-1536(5) and MODP-2048(14). Example: --kegroups=\"1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18\"")
	parser.add_argument("--fullalgs", action="store_true", help="Equivalent to known sets of encalgs, hashalgs, authmethods and keygroups (NOTE: This may take a while!)")
	parser.add_argument("--ikepath", type=str, help="The FULL ike-scan path if it is not in the PATH variable and/or the name changed.")
	parser.add_argument("-c", "--clientids", type=str, help="A file (dictionary) with a client ID per line to enumerate valid client IDs in Aggressive Mode. Default: unset - This test is not launched by default.")
	parser.add_argument("-n", "--nofingerprint", action="store_true", help="Do not attempt to fingerprint targets.")

	args = parser.parse_args()

	if args.target:
		if re.search(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', args.target):  # did not use \d shorthand since it searches ALL UNIX digits and is slower
			targets.append(args.target)
		else:
			print("\033[91m[*]\033[0m You need to specify a target in CIDR notation or an input file (-i).")
			parser.parse_args(["-h"])
			exit(1)

	if args.input:
		try:
			f = open(args.input, "r")
			targets.extend(f.read().splitlines())
			f.close()
		except:
			print("\033[91m[*]\033[0m The input file specified ('%s') could not be opened." % args.input)

	if args.output:
		try:
			f = open(args.output, "w")
			f.close()
		except:
			print("\033[91m[*]\033[0m The output file specified ('%s') could not be opened/created." % args.output)

	if not targets:
		print("\033[91m[*]\033[0m You need to specify a target in CIDR notation or an input file (-i).")
		parser.parse_args(["-h"])
		exit(1)

	if args.verbose:
		VERBOSE = True

	if args.ikepath:
		FULLIKESCANPATH = args.ikepath

	if args.encalgs:
		ENCLIST = args.encalgs.split()
		for alg in ENCLIST:
			parts = alg.split('/')
			for p in parts:
				if not p.isdigit():
					print("\033[91m[*]\033[0m Wrong syntax for the encalgs parameter. Check syntax.")
					parser.parse_args(["-h"])
					exit(1)
	
	if args.encalgsv2:
		ENCLISTv2 = args.encalgsv2.split()
		for alg in ENCLISTv2:
			parts = alg.split('/')
			for p in parts:
				if not p.isdigit():
					print("\033[91m[*]\033[0m Wrong syntax for the encalgs parameter. Check syntax.")
					parser.parse_args(["-h"])
					exit(1)

	if args.hashalgs:
		HASHLIST = args.hashalgs.split()
		for alg in HASHLIST:
			if not alg.isdigit():
				print("\033[91m[*]\033[0m Wrong syntax for the hashalgs parameter. Check syntax.")
				parser.parse_args(["-h"])
				exit(1)
	if args.hashalgsv2:
		HASHLISTv2 = args.hashalgsv2.split()
		for alg in HASHLISTv2:
			if not alg.isdigit():
				print("\033[91m[*]\033[0m Wrong syntax for the hashalgs parameter. Check syntax.")
				parser.parse_args(["-h"])
				exit(1)

	if args.authmethods:
		AUTHLIST = args.authmethods.split()
		for alg in AUTHLIST:
			if not alg.isdigit():
				print("\033[91m[*]\033[0m Wrong syntax for the authmethods parameter. Check syntax.")
				parser.parse_args(["-h"])
				exit(1)

	if args.kegroups:
		GROUPLIST = args.kegroups.split()
		for alg in GROUPLIST:
			if not alg.isdigit():
				print("\033[91m[*]\033[0m Wrong syntax for the kegroups parameter. Check syntax.")
				parser.parse_args(["-h"])
				exit(1)

	if args.xml:
		XMLOUTPUT = args.xml
	try:
		f = open(XMLOUTPUT, "w")
		f.close()
	except:
		print("\033[91m[*]\033[0m The XML output file could not be opened/created.")

	if args.clientids:
		try:
			f = open(args.clientids, "r")
			f.close()
			CLIENTIDS = args.clientids
		except:
			print("\033[91m[*]\033[0m The client ID dictionary could not be read. This test won't be launched.")

	if args.delay:
		DELAY = args.delay

	if args.fullalgs:
		ENCLIST = FULLENCLIST
		ENCLISTv2 = FULLENCLISTv2
		HASHLIST = FULLHASHLIST
		HASHLISTv2 = FULLHASHLISTv2
		AUTHLIST = FULLAUTHLIST
		GROUPLIST = FULLGROUPLIST

	return args, targets
	


###############################################################################
def printMessage(message, path=None):
	'''This method prints a message in the standard output and in the output file
	if it existed.
	@param message The message to be printed.
	@param path The output file, if specified.'''
	
	print(message)
	
	if path:
		try:
			f = open(path, "a")
			f.write("%s\n" % message)
			f.close()
		except:
			pass



###############################################################################
def launchProcess(command):
	'''Launch a command in a different process and return the process.'''
	
	process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	
	error = process.stderr.readlines()
	if len(error) > 0 and b"ERROR" in error[0] and b"port 500" in error[0]:
		printMessage("\033[91m[*]\033[0m Something was wrong! There may be another instance of ike-scan running. Ensure that there is no other process using ike-scan before to launch iker.")
		exit(1)

	process.wait()

	output = process.stdout.read().decode("utf-8")
	
	return output


###############################################################################
def delay(time):
	'''This method wait for a delay.
	@param time The time to wait in milliseconds.'''
	
	if time:
		sleep( time / 1000.0 )



###############################################################################
def waitForExit(args, vpns, ip, key, value):
	'''This method shows a progressbar during the discovery of transforms.
	@param top The total number of transforms combinations
	@param current The iteration within the bucle (which transform is checking).
	@param transform The string that represents the transform.'''

	try:
		printMessage("\033[91m[*]\033[0m You pressed Ctrl+C. Do it again to exit or wait to continue but skipping this step.")
		vpns[ip][key] = value
		sleep(2)
		if key not in list(vpns[ip].keys()) or not vpns[ip][key]:
			printMessage("[*] Skipping test...", args.output)
	except KeyboardInterrupt:
		parseResults(args, vpns)
		printMessage( "iker finished at %s" % strftime("%a, %d %b %Y %H:%M:%S +0000", localtime()), args.output )
		exit(0)



###############################################################################
def updateProgressBar(top, current, transform):
	'''This method shows a progressbar during the discovery of transforms.
	@param top The total number of transforms combinations
	@param current The iteration within the bucle (which transform is checking).
	@param transform The string that represent the transform.'''
	
	progressbar = "[....................] %d%% - Current transform: %s\r"
	tt = 20
	step = top / tt
	# Progress: [====================] 10% : DES-MD5
	cc = current / step
	progressbar = progressbar.replace(".", "=", int(cc))
	perctg = current * 100 / top
	
	#print progressbar %(perctg, transform),
	stdout.write(progressbar % (perctg, transform))
	stdout.flush()


###############################################################################
def checkIkeScan():
	'''This method checks for the ike-scan location.
	@return True if ike-scan was found and False in other case.'''

	proccess = subprocess.Popen("%s --version" % FULLIKESCANPATH, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	proccess.wait()

	output = proccess.stderr.read()
	output = str(output)

	if "ike-scan" in output.lower():
		return True
	else:
		return False


###############################################################################
def discovery(args, targets, vpns):
	'''Run ike-scan to discover IKE services and update the vpns variable with the information found.
	@param args The command line parameters
	@param targets The targets specified (IPs and/or networks)
	@param vpns A dictionary to store all the information'''
	
	printMessage("[*] Discovering IKE services, please wait...", args.output)
	
	# Launch ike-scan for each target and parse the output
	for target in targets:
		
		process_output = launchProcess("%s -M %s" % (FULLIKESCANPATH, target))
		
		ip = None
		info = ""
		
		for line in process_output.splitlines():
			if not line.split() or 'Starting ike-scan' in line or 'Ending ike-scan' in line:
				continue
			if line[0].isdigit():
				ip = line.split()[0]
				info = line
			else:
				info = info + line

		if info and ip not in list(vpns.keys()):
			vpns[ip] = {}
			vpns[ip]["handshake"] = info.strip()
			vpns[ip]["v1"] = True
			if VERBOSE:
				printMessage(info, args.output)
			else:
				printMessage("\033[92m[*]\033[0m IKE version 1 is supported by %s" % ip, args.output)



###############################################################################
def checkIKEv2(args, targets, vpns):
	'''This method checks if IKE version 2 is supported.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''
	
	printMessage("[*] Checking for IKE version 2 support...", args.output)
	ips = []
	
	try:
		# Check the IKE v2 support
		for target in targets:
			
			process_output = launchProcess("%s --ikev2 -M %s" % (FULLIKESCANPATH, target))
			
			ip = None
			info = ""
			no_ikev1=False
			for line in process_output.splitlines():
				if not line.split() or "Starting ike-scan" in line or "Ending ike-scan" in line:
					continue

				if line[0].isdigit():
					ip = line.split()[0]
					printMessage("\033[92m[*]\033[0m IKE version 2 is supported by %s" % ip, args.output)
					ips.append(ip)
					if ip in list(vpns.keys()):
						vpns[ip]["v2"] = True
						break
					else:
						vpns[ip] = {}
						vpns[ip]["v2"] = True
						vpns[ip]["v1"] = False
						vpns[ip]["v1"] = False
						no_ikev1=True
				else:
					printMessage("\033[91m[*]\033[0m IKE version 2 is not supported by %s" % target, args.output)
				info = info + line

			if no_ikev1:
				vpns[ip]["handshake"] = info
				printMessage("[*] IKE version 1 support was not identified in host %s" % ip, args.output)
				no_ikev1=False
		
		# Complete those that don't support it
		for ip in list(vpns.keys()):
			if "v2" not in list(vpns[ip].keys()):
				vpns[ip]["v2"] = False
	except KeyboardInterrupt:
		waitForExit(args, vpns, ip, "v2", False)
	

###############################################################################
def fingerprintVID(args, vpns, handshake=None):
	'''This method tries to discover the vendor of the devices by checking
	the VID. Results are written in the vpns variable.
	@param args The command line parameters
	@param vpns A dictionary to store all the information
	@param handshake The handshake where look for a VID'''
	
	for ip in list(vpns.keys()):
		
		if "vid" not in list(vpns[ip].keys()):
			vpns[ip]["vid"] = []
		
		# Fingerprint based on VIDs
		hshk = vpns[ip]["handshake"]
		if handshake:
			if ip in handshake:
				hshk = handshake
			else:
				continue
		
		transform = ""
		vid = ""
		for line in hshk.splitlines():
			if "SA=" in line:
				transform = line.strip()[4:-1]
			
			if "VID=" in line and "(" in line and ")" in line and "draft-ietf" not in line and "IKE Fragmentation" not in line and "Dead Peer Detection" not in line and "XAUTH" not in line and "RFC 3947" not in line and "Heartbeat Notify" not in line:
				
				vid = line[line.index("(")+1:line.index(")")]
		
		enc = False
		for pair in vpns[ip]["vid"]:
			if pair[0] == vid:
				enc = True
		
		if vid and not enc:
			vpns[ip]["vid"].append((vid, hshk))
			
			printMessage("\033[92m[*]\033[0m Vendor ID identified for IP %s with transform %s: %s" % (ip, transform, vid), args.output)


###############################################################################
def fingerprintShowbackoff(args, vpns, transform="", vpnip=""):
	'''This method tries to discover the vendor of the devices and the results
	are written in the vpns variable.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''
	
	printMessage( "\n[*] Trying to fingerprint the devices%s. This process is going to take a while (1-5 minutes per IP). Be patient..." % (transform and " (again)" or transform) , args.output)
	
	try:
		for ip in list(vpns.keys()):
			
			if vpnip and vpnip != ip:
				continue
			
			process_output = launchProcess("%s --showbackoff %s %s" % (FULLIKESCANPATH, ((transform and ("--trans="+transform) or transform)), ip))			

			vpns[ip]["showbackoff"] = ""
			
			# Fingerprint based on the VPN service behaviour
			for line in process_output.splitlines():
				if "Implementation guess:" in line:
					
					vendor = line[line.index('Implementation guess:')+22:].strip()
					
					if vendor.lower() != "unknown":
						
						vpns[ip]["showbackoff"] = vendor
					
						printMessage("\033[92m[*]\033[0m Implementation guessed for IP %s: %s" % (ip, vendor), args.output)
			
			if not vpns[ip]["showbackoff"]:
				if transform:
					printMessage("\033[91m[*]\033[0m The device %s could not been fingerprinted. It won't be retry again." % ip, args.output)
					vpns[ip]["showbackoff"] = " "
				else:
					printMessage("\033[91m[*]\033[0m The device %s could not been fingerprinted because no transform is known." % ip, args.output)
	except KeyboardInterrupt:
		waitForExit(args, vpns, ip, "showbackoff", " ")


###############################################################################
def checkEncryptionAlgs(args, vpns):
	'''This method tries to discover accepted transforms. The results
	are written in the vpns variable.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''
	
	try:
		top = len(ENCLIST) * len(HASHLIST) * len(AUTHLIST) * len(GROUPLIST)

		for ip in list(vpns.keys()):
			current=0
			printMessage( "\n[*] Looking for accepted IKEv1 transforms at %s" % ip, args.output)
			vpns[ip]["transforms"] = []
			
			for enc in ENCLIST:
				for hsh in HASHLIST:
					for auth in AUTHLIST:
						for group in GROUPLIST:
							
							process_output = launchProcess("%s -M --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, enc, hsh, auth, group, ip))
							#print("%s -M --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, enc, hsh, auth, group, ip))					
							info = ""
							new = False
							for line in process_output.splitlines():
								if "Starting ike-scan" in line or "Ending ike-scan" in line or line.strip() == "":
									continue
								
								info += line + "\n"
								if "SA=" in line:
									new = True
									transform = line.strip()[4:-1]
									printMessage("\033[92m[*]\033[0m Transform found: %s" % transform, args.output)
									printMessage("%s -M --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, enc, hsh, auth, group, ip), args.output)
							
							if new:
								vpns[ip]["transforms"].append(("%s,%s,%s,%s" % (enc,hsh,auth,group), transform, info) )
								fingerprintVID(args, vpns, info)
								# If the backoff could not been fingerprinted before...
								if not args.nofingerprint and not vpns[ip]["showbackoff"]:
									fingerprintShowbackoff(args, vpns, vpns[ip]["transforms"][0][0], ip)
							
							current += 1
							updateProgressBar(top, current, str(enc)+","+str(hsh)+","+str(auth)+","+str(group))
							delay(DELAY)
	except KeyboardInterrupt:
		if "transforms" not in list(vpns[ip].keys()) or not vpns[ip]["transforms"]:
			waitForExit(args, vpns, ip, "transforms", [])
		else:
			waitForExit(args, vpns, ip, "transforms", vpns[ip]["transforms"])

###############################################################################

def checkEncryptionAlgsv2(args, vpns):
	'''This method tries to discover accepted transforms. The results
	are written in the vpns variable.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''

	try:
		top = len(ENCLISTv2) * len(HASHLISTv2) * len(AUTHLIST) * len(GROUPLIST)
		# current = 0
		for ip in list(vpns.keys()):
			current = 0
			printMessage("\n[*] Looking for accepted IKEv2 transforms at %s" % ip, args.output)
			vpns[ip]["transformsv2"] = []

			for enc in ENCLISTv2:
				for hsh in HASHLISTv2:
					for auth in AUTHLIST:
						for group in GROUPLIST:

							process_output = launchProcess("%s -M --ikev2 --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, enc, hsh, auth, group, ip))

							info = ""
							new = False
							for line in process_output.splitlines():
								if "Starting ike-scan" in line or "Ending ike-scan" in line or line.strip() == "":
									continue

								line = line.strip()
								info += line + "\n"

								if "SA=" in line:
									new = True
									transform = line[4:-1]
									if "/" in enc: bits = enc.split("/")[1]
									else: bits = "-"
									printMessage("\033[92m[*]\033[0m Transform found: %s (Enc-bits: %s) %s" % (transform, bits, ip), args.output)
									printMessage("%s -M --ikev2 --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, enc, hsh, auth, group, ip), args.output)

							if new:
								vpns[ip]["transformsv2"].append(("%s, %s, %s, %s" % (enc, hsh, auth, group), transform, info))
								fingerprintVID(args, vpns, info)
								# If the backoff could not be fingerprinted before...
								if not args.nofingerprint and not vpns[ip]["showbackoff"]:
									fingerprintShowbackoff(args, vpns, vpns[ip]["transformsv2"][0][0], ip)

							current += 1
							updateProgressBar(top, current, str(enc)+","+str(hsh)+","+str(auth)+","+str(group))
							delay(DELAY)
	except KeyboardInterrupt:
		if "transformsv2" not in list(vpns[ip].keys()) or not vpns[ip]["transformsv2"]:
			waitForExit(args, vpns, ip, "transformsv2", [])
		else:
			waitForExit(args, vpns, ip, "transformsv2", vpns[ip]["transformsv2"])

###############################################################################
def checkAggressive(args, vpns):
	'''This method tries to check if aggressive mode is available. If so,
	it also store the returned handshake to a text file.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''
	
	try:
		top = len(ENCLIST) * len(HASHLIST) * len(AUTHLIST) * len(GROUPLIST)
		for ip in list(vpns.keys()):
			current = 0
			printMessage("\n[*] Looking for accepted IKEv1 transforms in aggressive mode at %s" % ip, args.output)
			vpns[ip]["aggressive"] = []
			
			for enc in ENCLIST:
				for hsh in HASHLIST:
					for auth in AUTHLIST:
						for group in GROUPLIST:
							
							process_output = launchProcess("%s -M --aggressive -P%s_handshake.txt --trans=%s,%s,%s,%s %s" % (FULLIKESCANPATH, ip, enc, hsh, auth, group, ip))

							info = ""
							new = False
							for line in process_output.splitlines():
								
								if "Starting ike-scan" in line or "Ending ike-scan" in line or line.strip() == "":
									continue
								
								info += line + "\n"
								
								if "SA=" in line:
									new = True
									transform = line.strip()[4:-1]
									printMessage("\033[92m[*]\033[0m Aggressive mode supported with transform: %s" % transform, args.output)
							
							if new:
								vpns[ip]["aggressive"].append(("%s,%s,%s,%s" % (enc,hsh,auth,group), transform, info) )
								fingerprintVID(args, vpns, info)
								# If the backoff could not been fingerprinted before...
								if not vpns[ip]["showbackoff"]:
									fingerprintShowbackoff(args, vpns, vpns[ip]["aggressive"][0][0], ip)
							
							current += 1
							updateProgressBar(top, current, str(enc)+","+str(hsh)+","+str(auth)+","+str(group))
							delay(DELAY)
	except KeyboardInterrupt:
		if "aggressive" not in list(vpns[ip].keys()) or not vpns[ip]["aggressive"]:
			waitForExit(args, vpns, ip, "aggressive", [])
		else:
			waitForExit(args, vpns, ip, "aggressive", vpns[ip]["aggressive"])



###############################################################################
def enumerateGroupIDCiscoDPD(args, vpns, ip):
	'''This method tries to enumerate valid client IDs from a dictionary.
	@param args The command line parameters
	@param vpns A dictionary to store all the information
	@param ip The ip where perform the enumeration'''
	
	# Check if possible
	
	process_output = launchProcess("%s --aggressive --trans=%s --id=badgroupiker573629 %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], ip))
	
	possible = True
	for line in process_output.splitlines():
		if "dead peer" in line.lower():
			possible = False
			break
	
	if possible:
		delay(DELAY)
		
		# Enumerate users
		try:
			fdict = open(args.clientids, "r")
			cnt = 0
			
			for cid in fdict:
				cid = cid.strip()
				
				process_output = launchProcess("%s --aggressive --trans=%s --id=%s %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], cid, ip))
				first_line_output=process_output.splitlines()[1].strip()

				
				# Check if the service is still responding 
				msg = sub(r'(HDR=\()[^\)]*(\))', r'\1xxxxxxxxxxx\2', first_line_output)
				if not msg:
					cnt += 1
					if cnt > 3:
						printMessage( "\033[91m[*]\033[0m The IKE service cannot be reached; a firewall might filter your IP address. DPD Group ID enumeration could not be performed...", args.output)
						return False
				
				enc = False
				for line in output:
					if "dead peer" in line.lower():
						enc = True
						break
				
				delay(DELAY)
				
				# Re-check the same CID if it looked valid
				if enc:
					process_output = launchProcess("%s --aggressive --trans=%s --id=%s %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], cid, ip))
					
					enc = False
					for line in process_output.splitlines():
						if "dead peer" in line.lower():
							vpns[ip]["clientids"].append(cid)
							printMessage( "\033[92m[*]\033[0m A potential valid client ID was found: %s" % cid, args.output)
							break
					
					delay(DELAY)
			
			fdict.close()
		except:
			possible = False
	
	return possible



###############################################################################
def enumerateGroupID(args, vpns):
	'''This method tries to enumerate valid client IDs from a dictionary.
	@param args The command line parameters
	@param vpns A dictionary to store all the information'''
	
	if not args.clientids:
		return
	
	
	for ip in list(vpns.keys()):
		
		vpns[ip]["clientids"] = []
		
		if not len(vpns[ip]["aggressive"]):
			continue
		
		printMessage( "\n[*] Trying to enumerate valid client IDs for IP %s" % ip, args.output)
		
		# Check if the device is vulnerable to Cisco DPD group ID enumeration and exploit it
		done = False
		if "showbackoff" in list(vpns[ip].keys()) and "cisco" in vpns[ip]["showbackoff"].lower():
			done = enumerateGroupIDCiscoDPD(args, vpns, ip)
		
		if "vid" in list(vpns[ip].keys()) and len(vpns[ip]["vid"]) > 0:
			for vid in vpns[ip]["vid"]:
				if "cisco" in vid[0].lower():
					done = enumerateGroupIDCiscoDPD(args, vpns, ip)
					break
		
		if done:
			#if not len (vpns[ip]["clientids"]):
			continue # If Cisco DPD enumeration, continue
		
		# Try to guess the "unvalid client ID" message
		process_output = launchProcess("%s --aggressive --trans=%s --id=badgroupiker123456 %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], ip))
		first_line_output=process_output.splitlines()[1].strip()
		message1 = sub(r'(HDR=\()[^\)]*(\))', r'\1xxxxxxxxxxx\2', first_line_output )
		
		delay(DELAY)
		
		process_output = launchProcess("%s --aggressive --trans=%s --id=badgroupiker654321 %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], ip))
		first_line_output=process_output.splitlines()[1].strip()
		message2 = sub(r'(HDR=\()[^\)]*(\))', r'\1xxxxxxxxxxx\2', first_line_output )
		
		delay(DELAY)
		
		process_output = launchProcess("%s --aggressive --trans=%s --id=badgroupiker935831 %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], ip))
		first_line_output=process_output.splitlines()[1].strip()
		message3 = sub(r'(HDR=\()[^\)]*(\))', r'\1xxxxxxxxxxx\2', first_line_output )
		
		delay(DELAY)
		
		invalidmsg = ""
		if message1 == message2:
			invalidmsg = message1
			if message1 != message3:
				vpns[ip]["clientids"].append("badgroupiker935831")
		elif message1 == message3:
			invalidmsg = message1
			vpns[ip]["clientids"].append("badgroupiker654321")
		elif message2 == message3:
			invalidmsg = message2
			vpns[ip]["clientids"].append("badgroupiker123456")
		else:
			printMessage( "\033[91m[*]\033[0m It was not possible to get a common response to invalid client IDs. This test will be skipped.", args.output)
			return
		
		# Enumerate users
		try:
			fdict = open(args.clientids, "r")
			cnt = 0
			
			for cid in fdict:
				cid = cid.strip()
				
				process_output = launchProcess("%s --aggressive --trans=%s --id=%s %s" % (FULLIKESCANPATH, vpns[ip]["aggressive"][0][0], cid, ip))
				first_line_output=process_output.splitlines()[1].strip()
				msg = sub(r'(HDR=\()[^\)]*(\))', r'\1xxxxxxxxxxx\2', first_line_output )
				
				if not msg:
					cnt += 1
					if cnt > 3:
						printMessage( "\033[91m[*]\033[0m The IKE service cannot be reached; a firewall might filter your IP address. Skippig to the following service...", args.output)
						break
					
				elif msg != invalidmsg:
					vpns[ip]["clientids"].append(cid)
					printMessage( "\033[92m[*]\033[0m A potential valid client ID was found: %s" % cid, args.output)
				
				delay(DELAY)
			
			fdict.close()
		except:
			pass

###############################################################################
def findTransformFlaw(args, fxml, transforms, flaw_string, flaw, announcement, announcement_text, flawid):
	first = True
	for trio in transforms:
		if flaw_string in trio[1]:
			if first:
				if not announcement:
					printMessage("\n[*] %s" % announcement_text)
					announcement = True
				first = False
				printMessage("\033[91m[*]\033[0m %s" % flaw, args.output)

			if VERBOSE:
				printMessage("%s" % trio[2], args.output)

			try:
				fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\" value=\"%s\"><![CDATA[%s]]></flaw>\n" % (flawid, flaw, trio[1], trio[2]))
				flawid += 1
			except:
				pass
	return flawid

		

def parseResults(args, vpns, startTime, endTime):
	'''This method analyzes the results and prints them where correspond.
	@param args The command line parameters
	@param vpns A dictionary to store all the information
	@param startTime A timestamp of when the script began
	@param endTime A timestamp of when the script finished'''


	ENC_ANNOUNCEMENT = False
	HASH_ANNOUNCEMENT = False
	KE_ANNOUNCEMENT = False
	AUTH_ANNOUNCEMENT = False
	ENC_ANNOUNCEMENT_TEXT = "Weak encryption algorithms are those considered broken by industry standards or key length is less than 128 bits."
	HASH_ANNOUNCEMENT_TEXT = "Weak hash algorithms are those considered broken by industry standards."
	KE_ANNOUNCEMENT_TEXT = "Weak key exchange groups are those considered broken by industry standards or modulus is less than 2048 bits."
	AUTH_ANNOUNCEMENT_TEXT = "Weak authentication methods are those not using multifactor authentication or not requiring mutual authentication."

	printMessage("\n\nResults:\n--------", args.output)

	pathxml = XMLOUTPUT

	try:
		fxml = open(pathxml, "a")
		fxml.write("<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n")
		fxml.write("<?time start=\"%s\" end=\"%s\" ?>\n" % (startTime, endTime))
		fxml.write("<best_practices>\n")
		fxml.write("\t<encryption algorithms=\"%s\"></encryption>\n" % ENC_ANNOUNCEMENT_TEXT)
		fxml.write("\t<hash algorithms=\"%s\"></hash>\n" % HASH_ANNOUNCEMENT_TEXT)
		fxml.write("\t<key_exchange groups=\"%s\"></key_exchange>\n" % KE_ANNOUNCEMENT_TEXT)
		fxml.write("\t<authentication methods=\"%s\"></authentication>\n" % AUTH_ANNOUNCEMENT_TEXT)
		fxml.write("</best_practices>\n")
		fxml.write("<services>\n")
	except:
		pass

	for ip in list(vpns.keys()):

		try:
			fxml.write("\t<service ip=\"%s\">\n\t\t<flaws>\n" % ip)
		except:
			pass

		# Discoverable
		printMessage("\nResults for IP %s:\n" % ip, args.output)
		printMessage("\033[91m[*]\033[0m %s" % FLAW_DISC, args.output)
		flawid = 0
		try:
			fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\"><![CDATA[%s]]></flaw>\n" % (flawid, FLAW_DISC, vpns[ip]["handshake"]))
			flawid += 1
		except:
			pass

		# IKE v1
		if "v1" in list(vpns[ip].keys()) and vpns[ip]["v1"]:
			printMessage("\033[91m[*]\033[0m %s" % FLAW_IKEV1, args.output)

			try:
				fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\"></flaw>\n" % (flawid, FLAW_IKEV1))
				flawid += 1
			except:
				pass

		# Fingerprinted by VID
		if "vid" in list(vpns[ip].keys()) and len(vpns[ip]["vid"]) > 0:

			printMessage("\033[91m[*]\033[0m %s" % FLAW_FING_VID, args.output)

			for pair in vpns[ip]["vid"]:

				printMessage("\t%s" % pair[0], args.output)
				if VERBOSE:
					printMessage("%s\n" % pair[1], args.output)

				try:
					fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\" value=\"%s\"><![CDATA[%s]]></flaw>\n" % (flawid, FLAW_FING_VID, pair[0], pair[1]))
					flawid += 1
				except:
					pass

		# Fingerprinted by back-off
		if "showbackoff" in list(vpns[ip].keys()) and vpns[ip]["showbackoff"].strip():

			printMessage("\033[91m[*]\033[0m %s: %s" % (FLAW_FING_BACKOFF, vpns[ip]["showbackoff"]), args.output)

			try:
				fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\" value=\"%s\"></flaw>\n" % (flawid, FLAW_FING_BACKOFF, vpns[ip]["showbackoff"]))
				flawid += 1
			except:
				pass

		# Weak encryption/hash/DH group algorithms and auth. methods

		if "transforms" in list(vpns[ip].keys()):
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=DES", FLAW_ENC_DES, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=IDEA", FLAW_ENC_IDEA, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=Blowfish", FLAW_ENC_BLOW, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=RC5", FLAW_ENC_RC5, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=CAST", FLAW_ENC_CAST, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Enc=3DES", FLAW_ENC_3DES, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Hash=MD5", FLAW_HASH_MD5, HASH_ANNOUNCEMENT, HASH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Hash=SHA1", FLAW_HASH_SHA1, HASH_ANNOUNCEMENT, HASH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Group=1:modp768", FLAW_DHG_1, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Group=2:modp1024", FLAW_DHG_2, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Group=5:modp1536", FLAW_DHG_5, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=PSK", FLAW_AUTH_PSK, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=DSS", FLAW_AUTH_DSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=RSA_Sig", FLAW_AUTH_RSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=RSA_Enc", FLAW_AUTH_RSA_ENC, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=RSA_RevEnc", FLAW_AUTH_RSA_ENC_REV, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ElGamel_Enc", FLAW_AUTH_ELG_ENC, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ElGamel_RevEnc", FLAW_AUTH_ELG_ENC_REV, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ECDSA_Sig", FLAW_AUTH_ECDSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ECDSA_SHA256", FLAW_AUTH_ECDSA_SHA256, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ECDSA_SHA384", FLAW_AUTH_ECDSA_SHA384, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=ECDSA_SHA512", FLAW_AUTH_ECDSA_SHA512, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=CRACK", FLAW_AUTH_CRACK, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=Hybrid_RSA", FLAW_AUTH_HYB_RSA, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transforms"], "Auth=Hybrid", FLAW_AUTH_HYB_DSA, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
		if "transformsv2" in list(vpns[ip].keys()):
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=DES", FLAW_ENC_DES, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=IDEA", FLAW_ENC_IDEA, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=Blowfish", FLAW_ENC_BLOW, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=RC5", FLAW_ENC_RC5, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=CAST", FLAW_ENC_CAST, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Enc=3DES", FLAW_ENC_3DES, ENC_ANNOUNCEMENT, ENC_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Hash=MD5", FLAW_HASH_MD5, HASH_ANNOUNCEMENT, HASH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Hash=SHA1", FLAW_HASH_SHA1, HASH_ANNOUNCEMENT, HASH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Group=1:modp768", FLAW_DHG_1, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Group=2:modp1024", FLAW_DHG_2, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Group=5:modp1536", FLAW_DHG_5, KE_ANNOUNCEMENT, KE_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=PSK", FLAW_AUTH_PSK, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=DSS", FLAW_AUTH_DSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=RSA_Sig", FLAW_AUTH_RSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=RSA_Enc", FLAW_AUTH_RSA_ENC, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=RSA_RevEnc", FLAW_AUTH_RSA_ENC_REV, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ElGamel_Enc", FLAW_AUTH_ELG_ENC, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ElGamel_RevEnc", FLAW_AUTH_ELG_ENC_REV, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ECDSA_Sig", FLAW_AUTH_ECDSA_SIG, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ECDSA_SHA256", FLAW_AUTH_ECDSA_SHA256, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ECDSA_SHA384", FLAW_AUTH_ECDSA_SHA384, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=ECDSA_SHA512", FLAW_AUTH_ECDSA_SHA512, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=CRACK", FLAW_AUTH_CRACK, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=Hybrid_RSA", FLAW_AUTH_HYB_RSA, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)
			flawid = findTransformFlaw(args, fxml, vpns[ip]["transformsv2"], "Auth=Hybrid", FLAW_AUTH_HYB_DSA, AUTH_ANNOUNCEMENT, AUTH_ANNOUNCEMENT_TEXT, flawid)

		# Aggressive Mode ?
		if "aggressive" in list(vpns[ip].keys()) and len(vpns[ip]["aggressive"]) > 0:

			printMessage("\033[91m[*]\033[0m %s" % FLAW_AGGR, args.output)

			for trio in vpns[ip]["aggressive"]:

				if VERBOSE:
					printMessage("%s" % (trio[2]), args.output)
				else:
					printMessage("\t%s" % (trio[1]), args.output)

				try:
					fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\" value=\"%s\"><![CDATA[%s]]></flaw>\n" % (flawid, FLAW_AGGR, trio[1], trio[2]))
					flawid += 1
				except:
					pass

			printMessage("\033[91m[*]\033[0m %s" % FLAW_AGGR_GRP_NO_ENC, args.output)
			try:
				fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\"></flaw>\n" % (flawid, FLAW_AGGR_GRP_NO_ENC))
				flawid += 1
			except:
				pass

		# Client IDs ?
		if "clientids" in list(vpns[ip].keys()) and len(vpns[ip]["clientids"]) > 0:

			printMessage("\033[91m[*]\033[0m %s: %s" % (FLAW_CID_ENUM, ", ".join(vpns[ip]["clientids"])), args.output)

			try:
				fxml.write("\t\t\t<flaw flawid=\"%s\" description=\"%s\" value=\"%s\"></flaw>\n" % (flawid, FLAW_CID_ENUM, ", ".join(vpns[ip]["clientids"])))
				flawid += 1
			except:
				pass

		try:
			fxml.write("\t\t</flaws>\n\t</service>\n")
		except:
			pass

	try:
		fxml.write("</services>\n")
		fxml.close()
	except:
		pass
	



###############################################################################
### Main method of the application
###############################################################################

def main():
	'''This is the main method of the application.'''
	
	# Say 'hello', check for privileges and ike-scan installation and parse the command line
	welcome()
	
	if not checkPrivileges():
		print("\033[91m[*]\033[0m This script requires root privileges.")
		exit(1)
	
	vpns = {}
	args, targets = getArguments()
	
	if not checkIkeScan():
		print("\033[91m[*]\033[0m ike-scan could not be found. Please specified the full path with the --ikepath option.")
		exit(1)
	
	startTime = strftime("%a, %d %b %Y %H:%M:%S %Z", localtime())
	printMessage("Starting iker at %s" % startTime, args.output)
	
	# 1. Discovery
	discovery( args, targets, vpns )
	checkIKEv2(args, targets, vpns)

	if not len(list(vpns.keys())):
		print("\033[93m[*]\033[0m No IKE service was found. Bye ;)")
		exit(0)
	
	# 2. Fingerprint by checking VIDs and by analysing the service responses
	fingerprintVID(args, vpns)
	if not args.nofingerprint:
		fingerprintShowbackoff(args, vpns)
	
	# 3. Ciphers
	checkEncryptionAlgs(args, vpns)
	
	# 4. Aggressive Mode
	checkAggressive(args, vpns)

	# 5. Ciphers IKEv2
	checkEncryptionAlgsv2(args, vpns)
	
	# 6. Enumerate client IDs
	enumerateGroupID(args, vpns)

	endTime = strftime("%a, %d %b %Y %H:%M:%S %Z", localtime())
	printMessage("iker finished enumerating/brute forcing at %s" % endTime, args.output)

	# . Parse the results
	parseResults(args, vpns, startTime, endTime)

if  __name__ =='__main__':
	main()



# Verde: \033[92m[*]\033[0m 
# Rojo: \033[91m[*]\033[0m 
# Amarillo: \033[93m[*]\033[0m