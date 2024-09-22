<header style="width: 100%; text-align: center; align-content: center; align-self: center; margin-bottom: 75px; color: #fff; text-decoration: none;">
        <nav>
            <a style="color: #fff; text-decoration: none; margin-right: 20px;" href="https://thecodecofficial.github.io/Blog/">Home</a>
            <a style="color: #fff; text-decoration: none; margin-right: 20px;" href="https://thecodecofficial.github.io/Blog/about.html">About</a>
        </nav>
    </header>
<div style="text-align:center"><h1>Reverse Engineering Blender's AgX Tonemapper</h1>
    <h6>
    	16. September 2024
    </h6>
</div>
<figure style="text-align: center">
  <img src="Images/colors_agx.jpg" style="width:100%">
</figure>

#### Motivation

With version 4, Blender came with a brand new set of color management options. Most notably, the AgX view transform was added as the default view transform. AgX is a tonemapper that compresses the high range of colors into a limited dynamic range for displaying them on a screen. It handles over-exposed areas much better than former approaches by producing similar responses to high intensities as real cameras.

I've been working on a simple raytracer recently. To get a nice cinematic look I thought I could implement AgX into my own pipeline. Looking into Blender's code I saw that it was implemented via a LUT, a look up table containing precomputed color values. This kind of bugged me as I couldn't figure out how to transform the raw rgb values from the raytracer to use in the LUT. Also, there must be some direct way to compute it, as all the values in the LUT had to have been computed somehow. After hours of research trying to figure out AgX's implementation I came up empty handed so I ultimately decided to create my own approximation for AgX. 

The main goal was to create a tonemapper that is similar to AgX and looks nice, everything else comes after that. So I didn't care about exact accuracy to the real AgX operator as long as it looked good and generally couldn't be discerned from the real one. Same with performance.

#### Tone Mapping

Standard rgb colors are usually defined in a range of $[0, 1]$ (or $0-255$ for integers). Many sources of color data such as renderers or even cameras very often go outside this range and output color values that are much larger than one. This is called high dynamic range (HDR). To view colors outside of the default range on a regular screen they need to be remapped back to $[0, 1]$. The process of remapping HDR to the standard dynamic range (SDR) is called tone mapping and a function $T:[0,\infin[\rightarrow[0,1]$ is called a tone mapping operator.

There are various tone mapping operators out there. In this post we'll only focus on global tone mapping operators, i.e. each pixel is mapped to another value independently of other pixels. Let's explore some existing tonemappers. We'll compare them by looking at a simple scene containing a ring of  emissive cylinders on a white plane. As a baseline, we'll set the intensity of the emission to one, so the final render should roughly be in SDR already.

<figure style="text-align: center">
  <img src="Images/colors_sdr.jpg" style="width:50%">
  <figcaption style="text-align: center">Scene (SDR)</figcaption>
</figure>

Now to actually see the effects of the tone mapping operators, we'll increase the intensity of each cylinder to 100.

- No tone mapping or **clamping** is the most trivial approach. We simply constrain all values to the range $[0, 1]$ and call it a day. This effectively discards all HDR information and thus looks quite bad in general. We can see that colors are blown out in bright areas and have a very abrupt falloff towards darker areas. The variety of colors also seems to be reduced: We can only make out around six shades. This is called the six colors problem or the Notorious Six. Additionally, clamping can create banding artifacts, as each color channel is clamped separately.

   <figure style="text-align: center">
      <img src="Images/colors_clip.jpg" style="width:25%">
      <figcaption style="text-align: center">Clamping/No Tone Mapping</figcaption>
    </figure>

- **Reinhard** tone mapping is defined as $T_\text{Reinhard}(l)=\frac{l}{l+1}$. This ensures that every value is mapped to the range $[0, 1]$. Note that $T_\text{Reinhard}$ is applied to the luminance $l$ of a pixel, and the rgb values are then changed based on the new luminance.

   <figure style="text-align: center">
      <img src="Images/colors_reinhard.jpg" style="width:25%">
      <figcaption style="text-align: center">(Simple) Reinhard Tone Mapping</figcaption>
    </figure>

- **Filmic** tone mapping is a collective term for a bunch of tone mapping operators that try to emulate the look of real film cameras. Taking the one from Blender as an example, we can see that this also greatly suffers from the six colors problem.

   <figure style="text-align: center">
      <img src="Images/colors_filmic.jpg" style="width:25%">
      <figcaption style="text-align: center">Filmic Tone Mapping (Blender)</figcaption>
    </figure>

- **ACES** stands for Academy Color Encoding System and is the industry standard for color management in movie and TV show production. It comes with its own tone mapper to display colors on SDR devices. ACES generally looks quite nice and is widely available in various renderers and game engines (e.g. Unreal Engine uses ACES as the default).

  <figure style="text-align: center">
      <img src="Images/colors_aces.jpg" style="width:25%">
      <figcaption style="text-align: center">ACES Tone Mapping (Hill)</figcaption>
    </figure>

  - **AgX** (from silver halide, a chemical used in photographic film) is currently the standard tonemapper in Blender. It was designed for better color management, replacing Blender's Filmic tone mapping. Bright areas are handled especially well and AgX doesn't suffer from the six colors problem. The resulting image might have some hue shifts and low contrast, but the latter can be fixed easily by further image processing.

    <figure style="text-align: center">
        <img src="Images/colors_agx.jpg" style="width:25%">
        <figcaption style="text-align: center">AgX Tone Mapping (Blender)</figcaption>
      </figure>

#### Looking at Existing Approximations

One popular implementation of ACES tone mapping is an approximation by Stephen Hill. First it transforms the raw input color into a color space defined by ACES. The values are then transformed in this new space according to a sigmoid-like function, followed by a transformation back to RGB. The sigmoid-like function (`RRTandODTFit` in the code snippet) is an approximative fit of the real RRT and ODT functions defined by ACES (the exact meaning of these functions is not important for this post). 

````c++
static const float3x3 ACESInputMat =
{
    {0.59719, 0.35458, 0.04823},
    {0.07600, 0.90834, 0.01566},
    {0.02840, 0.13383, 0.83777}
};

static const float3x3 ACESOutputMat =
{
    { 1.60475, -0.53108, -0.07367},
    {-0.10208,  1.10813, -0.00605},
    {-0.00327, -0.07276,  1.07602}
};

float3 RRTAndODTFit(float3 v)
{
    float3 a = v * (v + 0.0245786f) - 0.000090537f;
    float3 b = v * (0.983729f * v + 0.4329510f) + 0.238081f;
    return a / b;
}

float3 ACESFitted(float3 color)
{
    color = mul(ACESInputMat, color);
    color = RRTAndODTFit(color);
    color = mul(ACESOutputMat, color);

    return saturate(color); // Clamp to [0, 1]
}
````

 <p style="text-align: center">Hill ACES Tone Mapping (Simplified)</p>

In mathematical terms, we have the transformation matrices $T_{\text{ACES}_\text{in}}, T_{\text{ACES}_\text{out}}$ and a function $f_\text{RRT\_ODT}(c)= \frac{c \cdot (c + 0.0245786) - 0.000090537}{c \cdot (0.983729 \cdot c + 0.4329510) + 0.238081}$. The tone mapping operator is then defined as
$$
c_\text{out} =T_{\text{ACES}_\text{out}}\cdot f_\text{RRT\_ODT} (T_{\text{ACES}_\text{in}}\cdot c_\text{in})
$$
where $c_\text{in}, c_\text{out}$ are the input and output colors respectively.

#### Approximating AgX

I thought that this approach for the ACES tone mapping could be used for other tone mapping operators by replacing $f_\text{RRT\_ODT}$ with another function $f$. This essentially boils down to a tone mapping $f$ in the ACES color space. Through experimentation I found that a function similar to the Reinhard operator yields similar looking results to AgX when inserted into the equation.
$$
c_\text{out} =T_{\text{ACES}_\text{out}}\cdot f (T_{\text{ACES}_\text{in}}\cdot c_\text{in})\\
f(c):=\frac{c}{c+0.2}
$$
[IMAGE ACES, AgX, this, side by side]

It felt like I was getting closer to achieving the AgX look, so it was time to formulate this as an optimization problem. Let's modify $f$ to be more general: $f_{\alpha,\beta}(c)=\alpha\cdot\frac{c}{c+\beta}$. Additionally, let's introduce another transformation matrix $T_\text{shift}$ after $T_{\text{ACES}_\text{in}}$, to account for some interaction between the color channels (because $f_{\alpha,\beta}$ is applied to each channel separately and we might need to rotate the space first). So our final formula is
$$
c_\text{out} =T_{\text{ACES}_\text{out}}\cdot f_{\alpha,\beta} (T_\text{shift}\cdot T_{\text{ACES}_\text{in}}\cdot c_\text{in}).
$$
The objective for the optimization can be formulated as follows:
$$
\underset{\alpha,\beta,T}{\arg\min}\space ||c_\text{out}-c_\text{AgX}||_2\\
\underset{\alpha,\beta,T}{\arg\min}\space ||T_{\text{ACES}_\text{out}}\cdot f_{\alpha,\beta} (T_\text{shift}\cdot T_{\text{ACES}_\text{in}}\cdot c_\text{in})-c_\text{AgX}||_2\\
$$
Where $c_\text{AgX}$ is the true color corresponding to $c_\text{in}$ tone mapped via AgX.

#### Obtaining Data and Fitting

Next I needed some datapoints to fit to. For this I simply created a few scenes with a good variety of colors and intensities in Blender, rendered them and exported them as both raw and tonemapped (with AgX). To ensure that the data is as accurate as possible, I exported everything as an uncompressed (?) .exr file. This gets rid of any unwanted compression artifacts (and we don't have to worry about any gamma-correction related stuff). With the dataset ready, the last step was to actually fit the data.

There might be some neat way to solve the optimization and get the best result. However, a close solution is good enough and I really couldn't be bothered so I decided to use SciPy to solve it. Using BFGS yields following parameters:
$$
\alpha=0.98,\beta=0.2,
T_\text{shift}=
\begin{bmatrix}
1&0&0\\
0&1&0\\
0&0&1\\
\end{bmatrix}\\
\text{NOT THE ACTUAL VALUES}
$$
This completes our approximation of AgX tone mapping. When implementing it, we can combine the matrices $T_{\text{ACES}_\text{in}}$ and $T_\text{shift}$ into one to save a (somewhat) expensive matrix multiplication.

#### Results

- Comparisons

```python
def AgES_tonemap(x):
    AgES_input_mat = np.array(
        [
            [0.87973, 0.43996, 0.10074],
            [0.14475, 1.21123, 0.16654],
            [0.07477, 0.15437, 1.34944],
        ]
    )
    AgES_output_mat = np.array(
        [
            [1.60475, -0.53108, -0.07367],
            [-0.10208, 1.10813, -0.00605],
            [-0.00327, -0.07276, 1.07602],
        ]
    )

    x = np.dot(x, AgES_input_mat.T)
    x = 1.01841 * x / (x + 0.33286)
    x = np.dot(x, AgES_output_mat.T)
    x = np.clip(x, 0, 1)
    return x
```

 <p style="text-align: center">Python Implementation of AgES Tone Mapping</p>

#### References/Acknowledgements

- https://github.com/EaryChow/AgX?tab=readme-ov-file
- https://en.wikipedia.org/wiki/Silver_halide
- https://www.oscars.org/science-technology/sci-tech-projects/aces
- https://knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve/
- https://github.com/TheRealMJP/BakingLab/blob/master/BakingLab/ACES.hlsl
- https://64.github.io/tonemapping/



#### Contact

Questions and feedback are always welcome!

<div style="text-align: center">
    <a href="https://github.com/TheCodecOfficial"><img src="../icons/github-mark-white.svg" style="width:5%; margin: 50px;"></a>
    <a href="mailto:trutsch@student.ethz.ch"><img src="../icons/mail.png" style="width:5%; margin: 50px"></a>
    <!--<img src="../icons/discord-mark-white.svg" onclick="copyText()" style="width:5%; margin: 50px">
    <textarea id="textbox" style="display: none">TheCodec#2261</textarea>
</div>
<div style="text-align: center; display: none" id="copyInfo"><p>Copied Discord Username to Clipboard</p>-->
</div>
<webring-banner theme="dark" style="display: flex; justify-content: center; align-items: center;">
    <p>Member of the <a href="https://polyring.ch">Polyring</a> webring</p>
</webring-banner>
<script async src="https://polyring.ch/embed.js" charset="utf-8"></script>

