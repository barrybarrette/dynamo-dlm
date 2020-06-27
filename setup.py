from setuptools import setup, find_packages

with open('README.md', 'r') as readme_file:
    long_description = readme_file.read()

with open('requirements.txt', 'r') as requirements_file:
    requirements = [line.strip() for line in requirements_file.readlines()]

setup(
    name='dynamo-dlm',
    version='1.0.0',
    author='Barry Barrette',
    author_email='barrybarrette@gmail.com',
    description='Distributed lock manager for Python using AWS DynamoDB for persistence',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/whitebarry/dynamo-dlm',
    packages=find_packages(),
    install_requires=requirements
)
