import os
import setuptools


if getattr(setuptools, "__version__", "0") < "39":
    # v36.4.0+ needed to automatically include README.md in packaging
    # v38.6.0+ needed for long_description_content_type in setup()
    raise EnvironmentError(
        "Your setuptools is too old. "
        "Please run 'pip install --upgrade pip setuptools'."
    )


_THIS_DIR = os.path.dirname(os.path.realpath(__file__))


with open(os.path.join(_THIS_DIR, "README.md")) as f:
    _LONG_DESCRIPTION = f.read().strip()


__version__ = "0.1.6"


def main() -> None:
    setuptools.setup(
        name="citylex",
        version=__version__,
        author="Kyle Gorman",
        author_email="kylebgorman@gmail.com",
        description="Builds a multisource English lexicon",
        long_description=_LONG_DESCRIPTION,
        long_description_content_type="text/markdown",
        url="https://github.com/kylebgorman/citylex",
        keywords=[
            "computational linguistics",
            "morphology",
            "natural language processing",
            "phonology",
            "phonetics",
            "speech",
            "language",
        ],
        license="Apache 2.0",
        py_modules=["citylex", "citylex_pb2"],
        python_requires=">=3.6",
        zip_safe=False,
        install_requires=["pandas", "protobuf", "requests"],
        entry_points={"console_scripts": ["citylex = citylex:main"]},
        classifiers=[
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Development Status :: 3 - Alpha",
            "Environment :: Console",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
            "Topic :: Text Processing :: Linguistic",
        ],
    )


if __name__ == "__main__":
    main()
