package fairMTSP.main

import com.github.ajalt.clikt.core.CliktCommand
import com.github.ajalt.clikt.parameters.options.default
import com.github.ajalt.clikt.parameters.options.option
import com.github.ajalt.clikt.parameters.options.validate
import com.github.ajalt.clikt.parameters.types.int
import io.github.oshai.kotlinlogging.KotlinLogging
import java.io.File

private val log = KotlinLogging.logger {}
class CliParser : CliktCommand() {

    val instanceName: String by option(
        "-n",
        help = "instance name"
    ).default("bays29.tsp").validate {
        require(it.endsWith(".tsp")) {
            "provide a TSPLIB instance that ends in .tsp"
        }
    }

    val instancePath: String by option(
        "-p",
        help = "instance path"
    ).default("./data/").validate {
        require(File(instancePath + instanceName).exists()) {
            "file does not exist!!!"
        }
    }

    val numVehicles: Int by option(
        "-v",
        help = " number of Vehicles"
    ).int().default(2).validate {
        require(it >= 2 ) {
            "number of vehicles has to be >= 2"
        }
    }

    val outputPath: String by option(
        "-o",
        help = "path to file with output KPIs"
    ).default("./logs/results.yaml").validate {
        require(it.length > 5 && it.endsWith(".yaml")) {
            "output path should end with a non-empty file name and .yaml extension"
        }
    }

    override fun run() {
        log.info { "reading command line arguments..." }
    }
}