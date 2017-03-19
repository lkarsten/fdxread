
How to do a release
-------------------

https://setuptools.readthedocs.io/en/latest/setuptools.html#tagging-and-daily-build-or-snapshot-releases

* update CHANGES.rst
* update version in `libfdx/__init.py`.
* update version in `setup.py`. (Can't import from libfdx, chicken and egg situation)

*  python setup.py test && python setup.py sdist`
* commit and push, check that travis is still happy.

* Test package locally: In a fresh virtualenv, do `pip install ~/work/fdxread/dist/fdxread-0.x.x.tar.gz`

* Or, test via testpypi: ```
$ twine upload -r testpypi dist/fdxread-0.9.1.tar.gz

Uploading distributions to https://testpypi.python.org/pypi
Uploading fdxread-0.9.1.tar.gz
[================================] 113732/113732 - 00:00:04
```
and then install in a fresh virtualenv: `pip install --extra-index-url https://testpypi.python.org/simple/ fdxread`

* If everything looks good, git tag "fdxread-0.x.y" and push the tag.

* Final step: `twine upload dist/fdxread-0.x.y.tar.gz`

