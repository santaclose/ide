import re
import ast
import json
from futils import futils
import subprocess

def getFunctions(language, filePath):
	if language == "py":
		with open(filePath, 'r') as file:
			fileLines = [x for x in file.read().split('\n') if len(x) > 0]
		matches = []
		for i, line in enumerate(fileLines):
			match = re.findall(r'^def ([^:]+):$', line)
			if len(match) == 1:
				matches.append({"name": match[0], "line": i})
		return matches

def getClasses(language, filePath):
	if language == "py":
		with open(filePath, 'r') as file:
			fileLines = [x for x in file.read().split('\n') if len(x) > 0]
		matches = []
		for i, line in enumerate(fileLines):
			match = re.findall(r'^class ([^:]+):$', line)
			if len(match) == 1:
				matches.append({"name": match[0], "line": i, "functions": []})

		for foundClass in matches:
			i = foundClass["line"] + 1
			while i < len(fileLines) and fileLines[i][0] == '\t':
				match = re.findall(r'^\tdef ([^:]+):$', fileLines[i])
				if len(match) == 1:
					foundClass["functions"].append({"name": match[0], "line": i})
				i += 1


		return matches

def generateComponentGraph(language, folderPath, ignoreExternal=False, excludeDirs=[]):
	nFolderPath = futils.normalizePath(folderPath)
	res = {}
	if language == "py":
		internalModules = {x: x.replace(nFolderPath, '').replace('/', '.')[:-3] for x in futils.filesInFolderRec(folderPath) if not any([y in x for y in excludeDirs]) and x.endswith('.py')}
		for filePath in internalModules.keys():
			moduleName = internalModules[filePath]
			with open(filePath, 'r', encoding="utf-8") as file:
				contents = file.read().replace('\r', '')
				try:
					parentNode = ast.parse(contents)
					for node in ast.iter_child_nodes(parentNode):
						dependency = None
						if isinstance(node, ast.ImportFrom):
							dependency = node.module
						elif isinstance(node, ast.Import):
							dependency = node.names[0].name

						if dependency is None:
							continue

						if moduleName not in res.keys():
							res[moduleName] = set()

						if not ignoreExternal or dependency in internalModules.values():
							res[moduleName].add(dependency)
				except:
					pass
	elif language == "cpp":
		internalModules = {x: futils.removeExtension(x.replace(nFolderPath, '')) for x in futils.filesInFolderRec(folderPath) if not any([y in x for y in excludeDirs]) and (x.endswith('.cpp') or x.endswith('.hpp') or x.endswith('.c') or x.endswith('.h'))}
		for filePath in internalModules.keys():
			moduleName = internalModules[filePath]

			with open(filePath, 'r') as file:
				contents = file.read().replace('\r', '')

				absoluteIncludePattern = r'#include <([^<>]+)>'
				for match in re.findall(absoluteIncludePattern, contents):
					dependency = futils.removeExtension(match)
					if moduleName not in res.keys():
						res[moduleName] = set()
					if not ignoreExternal or dependency in internalModules.values():
						res[moduleName].add(dependency)

				relativeIncludePattern = r'#include "([^"]+)"'
				for match in re.findall(relativeIncludePattern, contents):
					currentPath = futils.getParentFolder(filePath)
					absolutePath = futils.resolve(currentPath, match)
					dependency = futils.removeExtension(absolutePath.replace(nFolderPath, ''))
					if moduleName not in res.keys():
						res[moduleName] = set()
					if not ignoreExternal or dependency in internalModules.values():
						if moduleName != dependency:
							res[moduleName].add(dependency)
	return res

def getEntryPoints(language, folderPath, excludeDirs=[]):
	res = set()
	if language == "py":
		toFind = 'if __name__ == "__main__"'
		internalModules = {x: x.replace(futils.normalizePath(folderPath), '').replace('/', '.')[:-3] for x in futils.filesInFolderRec(folderPath) if not any([y in x for y in excludeDirs]) and x.endswith('.py')}
		for filePath in internalModules.keys():
			moduleName = internalModules[filePath]
			with open(filePath, 'r', encoding="utf-8") as file:
				contents = file.read().replace('\r', '')
				if toFind in contents:
					res.add(moduleName)
	return res

def drawDirectedGraph(graph, entryPoints=set(), imageFormat="png"):
	graphvizText = "digraph G {"

	for k in graph.keys():
		if len(graph[k]) == 0:
			continue
		if k in entryPoints:
			graphvizText += f"	\"{k}\" [color=green]"
		graphvizText += f"	\"{k}\" -> {graph[k]}\n"

	graphvizText += "}"
	graphvizText = graphvizText.replace("'", '"')
	p = subprocess.Popen(['dot', f'-T{imageFormat}', '-o', f'graph.{imageFormat}'], stdin=subprocess.PIPE)    
	p.communicate(input=graphvizText.encode('utf-8'))
