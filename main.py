import math
import os
import sys
import time
from datetime import datetime

from github import Github
import threading
import urllib.request, json
import tokens
from github.GithubException import UnknownObjectException

g = Github(tokens.t1)
g1 = Github(tokens.t2)
g2 = Github(tokens.t3)

print("g " + str(g.get_rate_limit()))
print("g1 " + str(g1.get_rate_limit()))
print("g2 " + str(g2.get_rate_limit()))


queryString = "pushed:>=2017-01-01 language:javascript size:>=250000 followers:>=10"

request_repositories = g.search_repositories(query=queryString, sort="updated")
print(request_repositories.totalCount)


processedAllRepos = False

raw_repositories = []
repositories_to_check = []
packageUrls = []

pulledFromPagination = 0
totalRepositoriesQueried = 0
repositoriesWithPackageJson = 0
repositoriesWithReact = 0
repoPage = 0
# Setup Place to Dump Data:
filename = os.getcwd() + "\\Data\\" + str(datetime.fromtimestamp(time.time())).replace(":", "꞉")

f = open(filename + ".txt", "a")
f.write(queryString + '\n')
f.close()

def write_repository_data(repo_response):
    f = open(filename + ".txt", "a")
    f.write(repo_response + '\n')
    f.close()


def increment(count_label):
    if count_label == "queried":
        global totalRepositoriesQueried
        totalRepositoriesQueried += 1
    elif count_label == "json":
        global repositoriesWithPackageJson
        repositoriesWithPackageJson += 1
    elif count_label == "react":
        global repositoriesWithReact
        repositoriesWithReact += 1
    elif count_label == "page":
        global pulledFromPagination
        pulledFromPagination += 1
    elif count_label == "repo_page":
        global repoPage
        repoPage += 1

    update_values()


def update_values():
    sys.stdout.write("\r Page of Original Request:  " + str(repoPage))
    sys.stdout.write(" Pulled From Pagination: " + str(pulledFromPagination))
    sys.stdout.write(" Repos Queried: " + str(pulledFromPagination))
    sys.stdout.write(" Repos with Package.json: " + str(repositoriesWithPackageJson))
    sys.stdout.write(" Repos with React: " + str(repositoriesWithReact))

    sys.stdout.flush()


def get_repositories(lock):
    global raw_repositories
    for i in range(0, math.ceil(request_repositories.totalCount / 30)):
        try:
            lock.acquire()
            page = request_repositories.get_page(i)
            raw_repositories += page
            increment("repo_page")
            lock.release()
        except:
            print("limited")
            lock.release()


def get_links(lock):  # Get Repository Full Names

    while processedAllRepos == False:
        lock.acquire()
        repos = len(raw_repositories)
        lock.release()
        if repos > 0:
            lock.acquire()
            repo = raw_repositories.pop()
            repositories_to_check.append(repo.full_name)
            increment("page")
            lock.release()


def check_if_node_project(lock, git):
    while not processedAllRepos:
        lock.acquire()
        repositories_to_check_len = len(repositories_to_check)
        repo = None
        if repositories_to_check_len > 0:
            repo = repositories_to_check.pop()
        lock.release()
        if repositories_to_check_len > 0 and repo is not None:
            url = ""
            r = git.get_repo(repo)
            try:
                url = r.get_contents("package.json").download_url
            except UnknownObjectException:
                pass

            lock.acquire()
            if url != "":
                packageUrls.append((url, r.url))
                increment("json")
            increment("queried")
            lock.release()


def check_for_react(lock):
    while not processedAllRepos:
        if len(packageUrls) != 0:
            lock.acquire()
            repo = packageUrls.pop()
            lock.release()

            with urllib.request.urlopen(repo[0]) as url:
                data = json.loads(url.read().decode())
                if "dependencies" in data:
                    if "react" in data["dependencies"]:
                        lock.acquire()
                        increment("react")
                        write_repository_data(repo[1])
                        lock.release()


lock = threading.Lock()
process_repo_pages = threading.Thread(target=get_repositories, args=(lock,))

process_repos = threading.Thread(target=get_links, args=(lock,))

x = 2
threads = []
gits = [g1, g2]
for i in range(x):
    try:
        x = threading.Thread(target=check_if_node_project, args=(lock, gits[i]))
        threads.append(x)
    except RuntimeError:
        pass

check_for_react = threading.Thread(target=check_for_react, args=(lock,))

process_repo_pages.start()
process_repos.start()
for thread in threads:
    thread.start()
check_for_react.start()
