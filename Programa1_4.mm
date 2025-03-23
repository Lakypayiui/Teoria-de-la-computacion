#include <nanogui/nanogui.h>
#include <GLFW/glfw3.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <string>
#include <algorithm>
#include <sstream>
#include <chrono>
#include <sys/statvfs.h>
#include <Cocoa/Cocoa.h>
#include <cmath>
#include <iomanip>
#include <random>

#define GL_SILENCE_DEPRECATION
#define BUFFER_SIZE (8ULL * 1024ULL * 1024ULL * 1024ULL) // 8 GB en bytes

using namespace nanogui;
using namespace std::chrono;

std::string openSaveDialog() {
    @autoreleasepool {
        NSSavePanel* savePanel = [NSSavePanel savePanel];
        [savePanel setAllowedFileTypes:@[@"txt"]];
        [savePanel setAllowsOtherFileTypes:NO];
        [savePanel setNameFieldStringValue:@"combinaciones.txt"];
        [savePanel setTitle:@"Guardar combinaciones"];
        
        if ([savePanel runModal] == NSModalResponseOK) {
            NSURL* url = [savePanel URL];
            return std::string([[url path] UTF8String]);
        }
        return "";
    }
}

class CombinationGenerator {
private:
    size_t max_length;
    std::string output_filename;
    std::string count_filename;
    std::function<void(float)> progress_callback;
    std::atomic<float> progress{0.0f};
    std::ofstream log_file;

    void generateAndWriteBlock(std::ofstream& output_file, std::ofstream& count_file, size_t len, size_t start, size_t end, size_t total_combinations, size_t& written) {
        std::vector<std::string> buffer;
        size_t max_bytes_per_line = len + 1;
        size_t max_lines = BUFFER_SIZE / max_bytes_per_line;
        size_t lines_to_generate = std::min(end - start, max_lines);

        buffer.reserve(lines_to_generate);
        for (size_t i = start; i < start + lines_to_generate && i < end; ++i) {
            std::string combination(len, '0');
            for (size_t j = 0; j < len; ++j) {
                combination[len - 1 - j] = ((i >> j) & 1) ? '1' : '0';
            }
            buffer.push_back(combination);
        }

        size_t skip = 1;
        if (max_length > 25 && max_length < 27) skip = 100;
        else if (max_length > 27 && max_length < 30) skip = 300;
        else if (max_length > 30 && max_length < 32) skip = 500;
        else if (max_length > 32) skip = 1000;

        for (size_t i = 0; i < buffer.size(); i += (len <= 25 ? 1 : skip)) {
            const auto& combination = buffer[i];
            output_file << combination << '\n';
            size_t zeros = std::count(combination.begin(), combination.end(), '0');
            size_t ones = std::count(combination.begin(), combination.end(), '1');
            count_file << written + 1 << "." << zeros << "," << ones << ","
                       << std::fixed << std::setprecision(1) 
                       << (zeros > 0 ? std::log(static_cast<double>(zeros)) : -std::numeric_limits<double>::infinity()) << ","
                       << (ones > 0 ? std::log(static_cast<double>(ones)) : -std::numeric_limits<double>::infinity()) << '\n';
            written += (len <= 25 ? 1 : skip);
            progress.store(static_cast<float>(written) / total_combinations);
            progress_callback(progress.load());
        }
    }

public:
    CombinationGenerator(size_t n, const std::string& filename, std::function<void(float)> callback) 
        : max_length(n), output_filename(filename), progress_callback(callback) {
        log_file.open("execution_log.txt", std::ios::trunc);
        size_t last_slash = output_filename.find_last_of('/');
        count_filename = output_filename.substr(0, last_slash + 1) + "conteo.txt";
    }

    ~CombinationGenerator() {
        log_file.close();
    }

    uint64_t estimate_size() {
        uint64_t total_lines = 1; // ε
        for (size_t i = 1; i <= max_length; ++i) {
            total_lines += (1ull << i);
        }
        return total_lines * (max_length + 1);
    }

    std::string format_size(uint64_t bytes) {
        std::stringstream ss;
        ss << std::fixed << std::setprecision(2);
        double size = static_cast<double>(bytes);
        if (size < 1024) ss << size << " bytes";
        else if (size < 1024ULL * 1024) ss << (size / 1024) << " KB";
        else if (size < 1024ULL * 1024 * 1024) ss << (size / (1024ULL * 1024)) << " MB";
        else if (size < 1024ULL * 1024 * 1024 * 1024) ss << (size / (1024ULL * 1024 * 1024)) << " GB";
        else ss << (size / (1024ULL * 1024 * 1024 * 1024)) << " TB";
        return "Espacio necesario: " + ss.str();
    }

    bool check_disk_space(const std::string& path, uint64_t required_size) {
        struct statvfs stat;
        std::string dir_path = path.substr(0, path.find_last_of('/'));
        if (statvfs(dir_path.c_str(), &stat) != 0) return false;
        uint64_t free_space = (uint64_t)stat.f_bavail * stat.f_frsize;
        return free_space >= required_size * 2;
    }

    void generate() {
        auto start_time = high_resolution_clock::now();
        progress = 0.0f;

        std::ofstream output_file(output_filename, std::ios::trunc);
        std::ofstream count_file(count_filename, std::ios::trunc);
        size_t total_combinations = 1; // ε
        for (size_t len = 1; len <= max_length; ++len) {
            size_t combinations_len = 1ull << len;
            size_t skip = (len <= 25 ? 1 : (len > 26 && len < 27 ? 50 : (len > 27 && len < 30 ? 100 : (len > 30 && len < 32 ? 200 : 300))));
            total_combinations += combinations_len / skip + (combinations_len % skip != 0);
        }

        output_file << "ε\n";
        count_file << "1.0,0,-inf,-inf\n";
        size_t written = 1;
        progress.store(static_cast<float>(written) / total_combinations);
        progress_callback(progress.load());

        for (size_t len = 1; len <= max_length; ++len) {
            size_t total_combinations_len = 1ull << len;
            size_t max_bytes_per_line = len + 1;
            size_t max_lines_per_block = BUFFER_SIZE / max_bytes_per_line;

            for (size_t start = 0; start < total_combinations_len; start += max_lines_per_block) {
                size_t end = std::min(start + max_lines_per_block, total_combinations_len);
                generateAndWriteBlock(output_file, count_file, len, start, end, total_combinations, written);
            }
        }

        output_file.close();
        count_file.close();
        auto end_time = high_resolution_clock::now();
        auto duration = duration_cast<milliseconds>(end_time - start_time).count();
        log_file << "Generación completa - Tiempo total: " << duration << "ms\n";
    }
};

class CombinationApp : public nanogui::Screen {
private:
    std::queue<std::function<void()>> uiUpdates;
    std::mutex uiMutex;
    TextBox* fileBox;

    void plotData() {
        struct DataPoint {
            int lineNumber, zeros, ones;
            double logZeros, logOnes;
        };

        std::string base_path = fileBox->value();
        size_t last_slash = base_path.find_last_of('/');
        std::string directory = (last_slash == std::string::npos) ? "./" : base_path.substr(0, last_slash + 1);
        std::string count_filename = directory + "conteo.txt";
        std::string data_filename = directory + "datos_grafica.dat";
        std::string gnuplot_filename = directory + "graficar.gnuplot";
        std::string output_image = directory + "graficas.png";

        std::ifstream file(count_filename);
        if (!file) {
            queueUIUpdate([this]() {
                new MessageDialog(this, MessageDialog::Type::Warning, 
                    "Error", "No se pudo abrir el archivo conteo.txt");
            });
            return;
        }

        std::ofstream outFile(data_filename);
        if (!outFile) {
            queueUIUpdate([this]() {
                new MessageDialog(this, MessageDialog::Type::Warning, 
                    "Error", "No se pudo crear el archivo de datos para la gráfica");
            });
            return;
        }

        outFile << "# LineNumber Zeros Ones LogZeros LogOnes\n";
        std::string line;

        while (std::getline(file, line)) {
            DataPoint point;
            size_t periodPos = line.find(".");
            if (periodPos == std::string::npos) continue;

            std::string lineNumStr = line.substr(0, periodPos);
            std::stringstream(lineNumStr) >> point.lineNumber;

            size_t firstComma = line.find(",", periodPos);
            size_t secondComma = line.find(",", firstComma + 1);
            size_t thirdComma = line.find(",", secondComma + 1);

            if (firstComma == std::string::npos || secondComma == std::string::npos) continue;

            std::string zerosStr = line.substr(periodPos + 1, firstComma - periodPos - 1);
            std::string onesStr = line.substr(firstComma + 1, secondComma - firstComma - 1);

            zerosStr.erase(remove_if(zerosStr.begin(), zerosStr.end(), isspace), zerosStr.end());
            onesStr.erase(remove_if(onesStr.begin(), onesStr.end(), isspace), onesStr.end());

            std::stringstream(zerosStr) >> point.zeros;
            std::stringstream(onesStr) >> point.ones;

            if (thirdComma != std::string::npos) {
                std::string logZStr = line.substr(secondComma + 1, thirdComma - secondComma - 1);
                std::string logOStr = line.substr(thirdComma + 1);

                logZStr.erase(remove_if(logZStr.begin(), logZStr.end(), isspace), logZStr.end());
                logOStr.erase(remove_if(logOStr.begin(), logOStr.end(), isspace), logOStr.end());

                if (logZStr == "-inf") point.logZeros = std::numeric_limits<double>::quiet_NaN();
                else std::stringstream(logZStr) >> point.logZeros;

                if (logOStr == "-inf") point.logOnes = std::numeric_limits<double>::quiet_NaN();
                else std::stringstream(logOStr) >> point.logOnes;
            }

            outFile << point.lineNumber << " " << point.zeros << " " << point.ones << " "
                    << (std::isnan(point.logZeros) ? "NaN" : std::to_string(point.logZeros)) << " "
                    << (std::isnan(point.logOnes) ? "NaN" : std::to_string(point.logOnes)) << "\n";
        }

        file.close();
        outFile.close();

        std::ofstream gnuplotFile(gnuplot_filename);
        gnuplotFile << "set terminal png size 1200,800\n";
        gnuplotFile << "set output '" << output_image << "'\n";
        gnuplotFile << "set multiplot layout 2,2 title 'Graficas de ceros y unos'\n";
        gnuplotFile << "set xlabel 'Número de línea'\n";
        gnuplotFile << "set datafile missing 'NaN'\n";
        gnuplotFile << "set title 'Cantidad de Ceros'\n";
        gnuplotFile << "set ylabel 'Cantidad'\n";
        gnuplotFile << "plot '" << data_filename << "' using 1:2 with lines title 'Ceros'\n";
        gnuplotFile << "set title 'Cantidad de Unos'\n";
        gnuplotFile << "plot '" << data_filename << "' using 1:3 with lines title 'Unos'\n";
        gnuplotFile << "set title 'Logaritmo de Ceros'\n";
        gnuplotFile << "set ylabel 'Logaritmo'\n";
        gnuplotFile << "plot '" << data_filename << "' using 1:4 with lines title 'Log Ceros'\n";
        gnuplotFile << "set title 'Logaritmo de Unos'\n";
        gnuplotFile << "plot '" << data_filename << "' using 1:5 with lines title 'Log Unos'\n";
        gnuplotFile << "unset multiplot\n";
        gnuplotFile.close();

        std::string command = "gnuplot " + gnuplot_filename;
        system(command.c_str());

        // Abrir la imagen generada
        std::string open_command = "open \"" + output_image + "\"";
        system(open_command.c_str());

        queueUIUpdate([this, output_image]() {
            new MessageDialog(this, MessageDialog::Type::Information, 
                "Éxito", "Gráficas generadas y abiertas desde " + output_image);
        });
    }

public:
    CombinationApp() : Screen(Vector2i(400, 400), "Generador de Combinaciones", false) {
        Window* window = new Window(this, "Configuración");
        window->setPosition(Vector2i(15, 15));
        window->setLayout(new GroupLayout());

        new Label(window, "Longitud máxima:", "sans-bold");
        IntBox<int>* lenBox = new IntBox<int>(window);
        lenBox->setEditable(true);
        lenBox->setValue(3);
        lenBox->setMinMaxValues(0, 32);

        new Label(window, "Archivo de salida:", "sans-bold");
        fileBox = new TextBox(window);
        fileBox->setValue("combinaciones.txt");

        Button* browseButton = new Button(window, "Seleccionar...");
        browseButton->setCallback([this]() {
            std::string result = openSaveDialog();
            if (!result.empty()) fileBox->setValue(result);
        });

        ProgressBar* progressBar = new ProgressBar(window);
        progressBar->setValue(0.0f);

        Label* sizeLabel = new Label(window, "Espacio estimado: 0 bytes");

        Button* startButton = new Button(window, "Generar");
        Button* plotButton = new Button(window, "Graficar");
        Button* autoButton = new Button(window, "Modo Automático");

        startButton->setCallback([this, lenBox, progressBar, startButton, sizeLabel]() {
            startButton->setEnabled(false);
            size_t length = lenBox->value();
            
            auto check_and_run = [this, length, progressBar, startButton, sizeLabel]() {
                std::string filename = fileBox->value();
                CombinationGenerator generator(length, filename, [](float) {});
                uint64_t estimated_size = generator.estimate_size();
                
                std::stringstream ss;
                if (estimated_size < 1024) ss << estimated_size << " bytes";
                else if (estimated_size < 1024*1024) ss << (estimated_size/1024.0) << " KB";
                else if (estimated_size < 1024*1024*1024) ss << (estimated_size/(1024.0*1024)) << " MB";
                else ss << (estimated_size/(1024.0*1024*1024)) << " GB";
                sizeLabel->setCaption("Espacio estimado: " + ss.str());

                std::string size_message = generator.format_size(estimated_size);
                if (!generator.check_disk_space(filename, estimated_size)) {
                    auto* dialog = new MessageDialog(this, MessageDialog::Type::Warning, 
                        "Error", "No hay suficiente espacio en disco.\n" + size_message);
                    dialog->setCallback([startButton](int) {
                        startButton->setEnabled(true);
                    });
                } else {
                    run_generator(length, fileBox, progressBar, startButton, sizeLabel);
                }
            };

            CombinationGenerator temp_generator(length, fileBox->value(), [](float) {});
            std::string size_message = temp_generator.format_size(temp_generator.estimate_size());
            
            if (length > 10) {
                auto* dialog = new MessageDialog(this, MessageDialog::Type::Warning, 
                    "Advertencia", "El valor es grande y podría tardar mucho.\n" + size_message + "\n¿Continuar?");
                dialog->setCallback([this, check_and_run, startButton](int result) {
                    if (result == 0) check_and_run();
                    else startButton->setEnabled(true);
                });
            } else if (length == 0) {
                auto* dialog = new MessageDialog(this, MessageDialog::Type::Information, 
                    "Información", "Solo se generará ε.\n" + size_message);
                dialog->setCallback([this, check_and_run](int) { check_and_run(); });
            } else {
                auto* dialog = new MessageDialog(this, MessageDialog::Type::Information, 
                    "Información", size_message + "\n¿Continuar?");
                dialog->setCallback([this, check_and_run, startButton](int result) {
                    if (result == 0) check_and_run();
                    else startButton->setEnabled(true);
                });
            }
        });

        plotButton->setCallback([this]() { plotData(); });

        autoButton->setCallback([this, lenBox, progressBar, startButton, sizeLabel]() {
            startButton->setEnabled(false);
            std::random_device rd;
            std::mt19937 gen(rd());
            std::uniform_int_distribution<> dis(0, 25);
            size_t length = dis(gen);
            lenBox->setValue(length);

            std::string filename = fileBox->value();
            CombinationGenerator* generator = new CombinationGenerator(length, filename, 
                [this, progressBar](float value) {
                    queueUIUpdate([progressBar, value]() {
                        progressBar->setValue(std::min(value, 1.0f));
                    });
                });

            uint64_t estimated_size = generator->estimate_size();
            std::stringstream ss;
            if (estimated_size < 1024) ss << estimated_size << " bytes";
            else if (estimated_size < 1024*1024) ss << (estimated_size/1024.0) << " KB";
            else if (estimated_size < 1024*1024*1024) ss << (estimated_size/(1024.0*1024)) << " MB";
            else ss << (estimated_size/(1024.0*1024*1024)) << " GB";
            sizeLabel->setCaption("Espacio estimado: " + ss.str());

            std::thread([this, generator, startButton]() {
                generator->generate();
                plotData(); // Generar y abrir gráfica automáticamente
                queueUIUpdate([startButton]() { startButton->setEnabled(true); });
                delete generator;
            }).detach();
        });

        performLayout();
    }

    void queueUIUpdate(std::function<void()> update) {
        std::lock_guard<std::mutex> lock(uiMutex);
        uiUpdates.push(update);
    }

    void drawContents() override {
        std::lock_guard<std::mutex> lock(uiMutex);
        while (!uiUpdates.empty()) {
            uiUpdates.front()();
            uiUpdates.pop();
        }
        Screen::drawContents();
    }

private:
    void run_generator(size_t length, TextBox* fileBox, ProgressBar* progressBar, 
                      Button* startButton, Label* sizeLabel) {
        std::string filename = fileBox->value();
        
        CombinationGenerator* generator = new CombinationGenerator(length, filename, 
            [this, progressBar](float value) {
                queueUIUpdate([progressBar, value]() {
                    progressBar->setValue(std::min(value, 1.0f));
                });
            });

        uint64_t estimated_size = generator->estimate_size();
        std::stringstream ss;
        if (estimated_size < 1024) ss << estimated_size << " bytes";
        else if (estimated_size < 1024*1024) ss << (estimated_size/1024.0) << " KB";
        else if (estimated_size < 1024*1024*1024) ss << (estimated_size/(1024.0*1024)) << " MB";
        else ss << (estimated_size/(1024.0*1024*1024)) << " GB";
        sizeLabel->setCaption("Espacio estimado: " + ss.str());

        std::thread([this, generator, startButton]() {
            generator->generate();
            queueUIUpdate([startButton]() { startButton->setEnabled(true); });
            delete generator;
        }).detach();
    }
};

int main() {
    if (!glfwInit()) return -1;
    nanogui::init();
    CombinationApp* app = new CombinationApp();
    app->setVisible(true);
    app->drawAll();
    nanogui::mainloop(-1);
    delete app;
    nanogui::shutdown();
    glfwTerminate();
    return 0;
}