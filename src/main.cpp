/**
 * @file main.cpp
 * @brief Sequential implementation of Langton's Ant cellular automaton simulator.
 * 
 * This simulator implements a single-threaded version of Langton's Ant on a toroidal grid
 * with support for multiple agents (ants) and configurable output snapshots in PPM format.
 * 
 * @author Cocriș Iulian
 * @date June 2026
 * @version 1.0
 */

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

/**
 * @struct Ant
 * @brief Represents a single ant agent on the grid.
 * 
 * Each ant has a position (x, y), a direction, and a unique ID.
 * Directions: 0=North, 1=East, 2=South, 3=West
 */
struct Ant {
    int id;    ///< Unique agent identifier
    int x;     ///< X coordinate (column)
    int y;     ///< Y coordinate (row)
    int dir;   ///< Direction: 0=North, 1=East, 2=South, 3=West
    int steps_matching;
    int history_dir[104];
    int history_dx[104];
    int history_dy[104];
};

/**
 * @brief Write a snapshot of the grid to a PPM image file.
 * 
 * Creates a binary PPM (P6) image where white cells are (255,255,255), black cells
 * are (0,0,0), and ants are overlaid in red (255,0,0).
 * 
 * @param filename Output file path
 * @param grid Grid state (0=white, 1=black)
 * @param N Grid width/height
 * @param ants List of ants to overlay
 */
void write_ppm(const string &filename, const vector<uint8_t> &grid, int N, const vector<Ant> &ants) {
    vector<unsigned char> img(3 * N * N);
    for (int y = 0; y < N; ++y) {
        for (int x = 0; x < N; ++x) {
            int i = (y * N + x) * 3;
            if (grid[y * N + x] == 0) {
                img[i + 0] = 255;
                img[i + 1] = 255;
                img[i + 2] = 255;
            } else {
                img[i + 0] = 0;
                img[i + 1] = 0;
                img[i + 2] = 0;
            }
        }
    }

    for (const auto &a : ants) {
        int x = (a.x % N + N) % N;
        int y = (a.y % N + N) % N;
        int i = (y * N + x) * 3;
        img[i + 0] = 255;
        img[i + 1] = 0;
        img[i + 2] = 0;
    }

    ofstream ofs(filename, ios::binary);
    ofs << "P6\n" << N << " " << N << "\n255\n";
    ofs.write(reinterpret_cast<char *>(img.data()), static_cast<streamsize>(img.size()));
}

/**
 * @brief Main entry point for the sequential Langton's Ant simulator.
 * 
 * Command-line options:
 * - `-n, --size`: Grid size (N×N), default 200
 * - `-t, --steps`: Number of simulation steps, default 10000
 * - `-a, --ants`: Number of ants, default 1
 * - `-k, --snapshot`: Write PPM snapshot every K steps (0=only final), default 0
 * - `--no-wrap`: Disable toroidal wrapping
 * 
 * @param argc Argument count
 * @param argv Argument vector
 * @return 0 on success, non-zero on error
 */
int main(int argc, char **argv) {
    int N = 200;
    long long T = 10000;
    int ants_n = 1;
    int snapshot_k = 0;
    bool wrap = true;
    bool gui_mode = false;

    for (int i = 1; i < argc; ++i) {
        string s = argv[i];
        if ((s == "-n" || s == "--size") && i + 1 < argc) {
            N = stoi(argv[++i]);
        } else if ((s == "-t" || s == "--steps") && i + 1 < argc) {
            T = atoll(argv[++i]);
        } else if ((s == "-a" || s == "--ants") && i + 1 < argc) {
            ants_n = stoi(argv[++i]);
        } else if ((s == "-k" || s == "--snapshot") && i + 1 < argc) {
            snapshot_k = stoi(argv[++i]);
        } else if (s == "--no-wrap") {
            wrap = false;
        } else if (s == "-g" || s == "--gui") {
            gui_mode = true;
        } else if (s == "-h" || s == "--help") {
            cout << "Usage: " << argv[0] << " [-n size] [-t steps] [-a ants] [-k snapshot_freq] [--no-wrap] [-g|--gui]\n";
            return 0;
        }
    }

    vector<uint8_t> grid(N * N, 0);
    vector<Ant> ants;
    int cx = N / 2, cy = N / 2;
    for (int i = 0; i < ants_n; ++i) {
        Ant a;
        a.id = i;
        a.x = cx + (i % 3) - 1;
        a.y = cy + (i / 3) - 1;
        a.dir = 0;
        a.steps_matching = 0;
        for (int j = 0; j < 104; ++j) {
            a.history_dir[j] = -1;
            a.history_dx[j] = 99;
            a.history_dy[j] = 99;
        }
        ants.push_back(a);
    }

    if (gui_mode) {
        cout << "INIT " << N << " " << ants_n << " 1" << endl;
        for (const auto &a : ants) {
            cout << "ANT " << a.id << " " << a.x << " " << a.y << " " << a.dir << endl;
        }
        cout << "START" << endl;
        cout.flush();
    }

    auto in_bounds = [&](int x, int y) { return x >= 0 && x < N && y >= 0 && y < N; };

    for (long long step = 1; step <= T; ++step) {
        if (gui_mode) {
            cout << "STEP " << step << endl;
        }
        for (auto &a : ants) {
            int x = a.x, y = a.y;
            if (!wrap && !in_bounds(x, y)) {
                continue;
            }

            int gx = (x % N + N) % N;
            int gy = (y % N + N) % N;
            uint8_t color = grid[gy * N + gx];
            if (color == 0) {
                a.dir = (a.dir + 1) % 4;
            } else {
                a.dir = (a.dir + 3) % 4;
            }
            grid[gy * N + gx] = 1 - color;

            if (gui_mode) {
                cout << "FLIP " << gx << " " << gy << " " << (int)(1 - color) << endl;
            }

            int step_dx = 0;
            int step_dy = 0;
            if (a.dir == 0) {
                a.y -= 1;
                step_dy = -1;
            } else if (a.dir == 1) {
                a.x += 1;
                step_dx = 1;
            } else if (a.dir == 2) {
                a.y += 1;
                step_dy = 1;
            } else {
                a.x -= 1;
                step_dx = -1;
            }

            if (wrap) {
                a.x = (a.x % N + N) % N;
                a.y = (a.y % N + N) % N;
            }

            if (gui_mode) {
                cout << "ANT " << a.id << " " << a.x << " " << a.y << " " << a.dir << endl;
            }

            // Highway detection history update
            int idx = (step - 1) % 104;
            if (a.history_dir[idx] == a.dir && a.history_dx[idx] == step_dx && a.history_dy[idx] == step_dy) {
                a.steps_matching++;
            } else {
                a.steps_matching = 0;
            }
            a.history_dir[idx] = a.dir;
            a.history_dx[idx] = step_dx;
            a.history_dy[idx] = step_dy;
        }

        bool highway_detected = false;
        for (const auto &a : ants) {
            if (a.steps_matching >= 208) {
                highway_detected = true;
                break;
            }
        }
        if (highway_detected) {
            cout << "Highway detected at step " << step << ". Stopping simulation." << endl;
            T = step;
            break;
        }

        if (gui_mode) {
            int black = 0;
            for (uint8_t c : grid) if (c == 1) black++;
            int white = N * N - black;
            cout << "STATS " << black << " " << white << " 0" << endl;
            cout.flush();
        }

        if (snapshot_k > 0 && step % snapshot_k == 0) {
            char buf[256];
            snprintf(buf, sizeof(buf), "output_step_%06lld.ppm", step);
            write_ppm(buf, grid, N, ants);
        }
    }

    write_ppm("output_final.ppm", grid, N, ants);
    if (gui_mode) {
        cout << "FINISHED" << endl;
        cout.flush();
    }
    cout << "Simulation complete. Output: output_final.ppm" << endl;
    return 0;
}
