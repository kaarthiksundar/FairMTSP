## Fair Multiple Traveling Salesmam Problem (MTSP)

Code for computational experiments of the paper
"Equitable Routing - Rethinking the Mutiple Traveling Salesman Problem" be made available in arXiv.

[//]: # ([Arxiv]&#40;https://arxiv.org/abs/1912.04353&#41;.)
It presents new formulations to enforce fairness in the distribution of tour lengths in the MTSP.

## Branches

The _master_ branch contains all solver code and can be used to run either
algorithm with any of the instances available in the "app/data" folder. See the
"Running the solver" section for further details. The "readResults" folder
contains scripts to generate the results reported in the paper (also available in the
"results" folder).

## Dependencies

- CPLEX
- Gradle (installation optional, wrapper included)

## Usage

Clone the repository. If not already present, create the file
"~/.gradle/gradle.properties". Add the following two lines to the file:

```
cplexJarPath=/file/path/to/cplex/jar
cplexLibPath=/folder/path/to/cplex/library
```

The key `cplexJarPath` specifies the complete path to the CPLEX JAR file. It
must end with `cplex.jar`. The `cplexLibPath` should point to the path that
holds the CPLEX library (file with dll/a/so extension). This path should be a
folder path and NOT a file path. It usually points to a folder within the CPLEX
bin folder. For example, the paths could look like so on a Mac:

```
cplexJarPath=/Applications/CPLEX_Studio2211/cplex/lib/cplex.jar
cplexLibPath=/Applications/CPLEX_Studio2211/cplex/bin/x86-64_osx
```

Open a terminal and make the `./gradlew` file executable if necessary. Run
`./gradlew build` to compile and `./gradlew run` to run the code. The latter
task can also be run directly. Another useful task is `./gradlew clean`, which
cleans the gradle build files. If Gradle is installed, `./gradlew` can be
replaced with `gradle` in all the above commands.

## Running with Intellij

- Open Intellij, select "Import Project" and point it to the repo path.
- Select "Import Project from external model -> Gradle".
- Check the following checkboxes:
    + "Use auto-import"
    + "Create directories for empty content roots automatically"
- Select the "Use default gradle wrapper"
- Clock on the "Finish" button on the bottom right.

That's it, nothing else is needed. Ignore complaints about modules that were
removed. To run the project for the first time, select
"View -> Tool Windows -> Gradle". The Gradle window should open up on the
right. Expand the tree and double-click on "Tasks -> application -> run". For
subsequent runs, we can continue doing the same thing, or select this
configuration from the "Run" menu. Debugging can also be done with this
configuration from the same menu. After the first run, this task will show up
as something like "Run project-name [run]" and "Debug project-name [run]" in
the "Run" menu, where "project-name" is the name of the project.

## Running the solver

The solver is designed to read one of the instances files from the "app/data" folder,
solve the problem with the algorithms presented in the paper limited to 1 hour of run-time
and write results to "app/logs/". By default, it selects the instance
"app/data/seattle.tsp". To see if everything works, follow the instructions
in the "Usage" section above and try `./gradlew run`. Some logs should be visible
in the console and the result file should be generated in about 2 minutes. Run
configuration can be changed with available command-line arguments. To view them,
run `./gradlew run --args="-h"`. Any arguments can be passed in a similar way.
For example, to run the default instance with branch-and-cut, use the command
`./gradlew run"`. To work through the code flow, start from "App.kt".

## Additional notes

CPLEX and other dependencies have been set up correctly in "build.gradle".
In case some dependencies need access to config files, the files can be placed
in "app/src/main/resources". This folder already holds "simplelogger.properties", the config
file for the "simplelogger" logging utility.

## License

MIT License. See LICENSE file for details.